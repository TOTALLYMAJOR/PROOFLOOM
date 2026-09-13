import crypto from "node:crypto";
import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import AxeBuilder from "@axe-core/playwright";
import { chromium, firefox, webkit } from "@playwright/test";
import pixelmatch from "pixelmatch";
import { PNG } from "pngjs";


const CONTENT_TYPES = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
};

const BROWSER_TYPES = { chromium, firefox, webkit };
const SUPPORTED_BROWSERS = Object.freeze(Object.keys(BROWSER_TYPES));


export function normalizeBrowserPolicy(scenario, requestedBrowsers = []) {
  const declared = scenario.browserPolicy || {};
  const required = requestedBrowsers.length
    ? requestedBrowsers
    : (declared.required || ["chromium"]);
  const browsers = [...new Set(required.flatMap((item) => item === "all" ? SUPPORTED_BROWSERS : String(item).split(",")).map((item) => item.trim()).filter(Boolean))];
  const unsupported = browsers.filter((item) => !SUPPORTED_BROWSERS.includes(item));
  if (unsupported.length) throw new Error(`Unsupported browser(s): ${unsupported.join(", ")}`);
  if (!browsers.length) throw new Error("At least one browser is required");
  const baselineBrowser = declared.baselineBrowser || "chromium";
  if (!SUPPORTED_BROWSERS.includes(baselineBrowser)) throw new Error(`Unsupported baseline browser: ${baselineBrowser}`);
  return { browsers, baselineBrowser };
}


export function resolveBaselineEntry(baselineManifest, scenarioId, browserName, viewportId, baselineBrowser = "chromium") {
  const scenarioEntry = baselineManifest.scenarios?.[scenarioId];
  const browserEntry = scenarioEntry?.browsers?.[browserName]?.viewports?.[viewportId];
  if (browserEntry) return { entry: browserEntry, source: "browser-scoped" };
  if (browserName === baselineBrowser) {
    const legacyEntry = scenarioEntry?.viewports?.[viewportId];
    if (legacyEntry) return { entry: legacyEntry, source: "legacy-baseline-browser" };
  }
  return { entry: null, source: "none" };
}


export async function runScenario({
  scenarioPath,
  repositoryRoot = process.cwd(),
  sourceRoot = repositoryRoot,
  outputRoot,
  allowMissingBaseline = false,
  baseURL: suppliedBaseURL,
  browserName = "chromium",
  browserScopedArtifacts = false,
}) {
  const root = path.resolve(repositoryRoot);
  const source = path.resolve(sourceRoot);
  const scenario = await readJson(path.resolve(root, scenarioPath));
  const thresholds = await readJson(path.resolve(root, scenario.thresholds || ".design/quality/thresholds.json"));
  const output = path.resolve(root, outputRoot || scenario.artifactRoot || "artifacts/design");
  const baselineManifest = await readJson(path.resolve(root, scenario.baselineManifest || ".design/baselines/manifest.json"), {
    schemaVersion: 1,
    scenarios: {},
  });
  let server;
  let baseURL = suppliedBaseURL || scenario.baseURL;
  if (!baseURL && scenario.staticRoot) {
    server = await startStaticServer(path.resolve(root, scenario.staticRoot));
    baseURL = server.baseURL;
  }
  if (!baseURL) {
    throw new Error("Scenario requires baseURL or staticRoot");
  }

  const policy = normalizeBrowserPolicy(scenario, [browserName]);
  const selectedBrowser = policy.browsers[0];
  let browser;
  const viewportResults = [];
  const findings = [];
  const currentScreenshots = [];
  const baselineScreenshots = [];
  try {
    browser = await BROWSER_TYPES[selectedBrowser].launch({ headless: true });
    for (const viewport of scenario.viewports) {
      const result = await inspectViewport({
        browser,
        root,
        output,
        scenario,
        viewport,
        baseURL,
        baselineManifest,
        thresholds,
        allowMissingBaseline,
        browserName: selectedBrowser,
        baselineBrowser: policy.baselineBrowser,
        browserScopedArtifacts,
      });
      viewportResults.push(result.summary);
      findings.push(...result.findings);
      currentScreenshots.push(result.currentScreenshot);
      if (result.baselineScreenshot) baselineScreenshots.push(result.baselineScreenshot);
    }
  } finally {
    if (browser) await browser.close();
    if (server) await server.close();
  }

  const totals = summarize(viewportResults);
  const status = findings.some((item) => ["P0", "P1"].includes(item.severity)) ? "FAIL" : findings.length ? "WARN" : "PASS";
  const generatedAt = new Date().toISOString();
  const report = {
    schemaVersion: 1,
    scenario: scenario.id,
    surface: scenario.surface,
    route: scenario.route,
    browser: selectedBrowser,
    generatedAt,
    commitSha: gitSha(source),
    sourceRevision: {
      repository: path.basename(source),
      branch: gitBranch(source),
      commitSha: gitSha(source),
    },
    status,
    repairIterations: Number(scenario.repairIterations || 0),
    thresholds,
    viewports: viewportResults,
    totals,
    findings,
    evidenceBoundary: "Browser-explicit deterministic DOM, accessibility, containment, contract, and browser-scoped pixel evidence. Manual semantic and model visual review remain separate.",
  };
  const reportDirectory = path.join(output, "reports", scenario.id, ...(browserScopedArtifacts ? [selectedBrowser] : []));
  await fs.mkdir(reportDirectory, { recursive: true });
  const reportPath = path.join(reportDirectory, "qa-report.json");
  await writeJson(reportPath, report);
  const reviewManifest = {
    surface: scenario.surface,
    source: "playwright",
    covered_viewports: [...new Set(scenario.viewports.map((item) => item.category))],
    before_screenshots: baselineScreenshots.map((item) => relative(root, item)),
    after_screenshots: currentScreenshots.map((item) => relative(root, item)),
    viewport_findings: findings.map((item) => ({
      viewport: item.viewportCategory,
      severity: item.severity,
      root_cause: item.rootCause,
      evidence: item.message,
      preserve: item.preserve || [],
      change: item.change || [],
      repairable: Boolean(item.repairable),
      source: item.source,
      evidence_id: item.id,
    })),
    remaining_debt: [],
    automated_accessibility: status === "PASS" ? "PASS" : "FAIL",
    manual_semantic_review: "REQUIRED",
  };
  const reviewPath = path.join(reportDirectory, "review-manifest.json");
  await writeJson(reviewPath, reviewManifest);
  return { report, reportPath, reviewPath };
}


export async function runCrossBrowserScenario(options) {
  const root = path.resolve(options.repositoryRoot || process.cwd());
  const scenario = await readJson(path.resolve(root, options.scenarioPath));
  const policy = normalizeBrowserPolicy(scenario, options.browsers || []);
  const results = [];
  for (const browserName of policy.browsers) {
    try {
      results.push(await runScenario({
        ...options,
        browserName,
        browserScopedArtifacts: true,
        allowMissingBaseline: browserName !== policy.baselineBrowser || options.allowMissingBaseline,
      }));
    } catch (error) {
      results.push({
        report: {
          browser: browserName,
          status: "BLOCKED",
          totals: null,
          viewports: [],
          blocker: error.message,
        },
        reportPath: null,
      });
    }
  }
  const reports = results.map((item) => item.report);
  const status = reports.some((item) => item.status === "BLOCKED") ? "BLOCKED" : reports.some((item) => item.status === "FAIL") ? "FAIL" : reports.some((item) => item.status === "WARN") ? "WARN" : "PASS";
  const aggregate = {
    schemaVersion: 1,
    kind: "design-intelligence/cross-browser-evidence",
    scenario: scenario.id,
    generatedAt: new Date().toISOString(),
    status,
    requiredBrowsers: policy.browsers,
    baselineBrowser: policy.baselineBrowser,
    browsers: reports.map((report, index) => ({
      browser: report.browser,
      status: report.status,
      totals: report.totals,
      reportPath: results[index].reportPath ? relative(root, results[index].reportPath) : null,
      governedVisualViewports: report.viewports.filter((item) => item.visual.governed).length,
      structuralViewports: report.viewports.length,
      blocker: report.blocker || null,
    })),
    allRequiredBrowsersExecuted: reports.length === policy.browsers.length && reports.every((report) => report.status !== "BLOCKED"),
    baselineIsolation: "Legacy baselines apply only to baselineBrowser; other engines require separately approved browser-scoped entries.",
    evidenceBoundary: "Cross-browser execution is local browser evidence, not hosted availability, customer acceptance, or production outcome proof.",
  };
  const output = path.resolve(root, options.outputRoot || scenario.artifactRoot || "artifacts/design");
  const aggregatePath = path.join(output, "reports", scenario.id, "cross-browser-report.json");
  await writeJson(aggregatePath, aggregate);
  return { report: aggregate, reportPath: aggregatePath, browserResults: results };
}


async function inspectViewport({
  browser,
  root,
  output,
  scenario,
  viewport,
  baseURL,
  baselineManifest,
  thresholds,
  allowMissingBaseline,
  browserName,
  baselineBrowser,
  browserScopedArtifacts,
}) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 1,
    colorScheme: "light",
    reducedMotion: "reduce",
    locale: "en-US",
    timezoneId: "UTC",
  });
  const page = await context.newPage();
  const route = new URL(scenario.route || "/", baseURL).href;
  await page.goto(route, { waitUntil: "domcontentloaded" });
  await page.locator(scenario.readinessSelector || "body").waitFor({ state: "visible" });
  await page.addStyleTag({
    content: "*,*::before,*::after{animation-duration:0s!important;transition-duration:0s!important;caret-color:transparent!important}",
  });
  await runInteractions(page, scenario.interactions || []);

  const browserSegments = browserScopedArtifacts ? [browserName] : [];
  const artifactBase = path.join(output, "screenshots", scenario.id, ...browserSegments, viewport.id);
  const currentScreenshot = path.join(artifactBase, "current.png");
  const fullScreenshot = path.join(artifactBase, "full.png");
  await fs.mkdir(artifactBase, { recursive: true });
  await page.screenshot({ path: currentScreenshot, fullPage: false, animations: "disabled" });
  await page.screenshot({ path: fullScreenshot, fullPage: true, animations: "disabled" });

  const dom = await captureDom(page, scenario);
  const axe = await new AxeBuilder({ page }).analyze();
  const domPath = path.join(output, "DOM", scenario.id, ...browserSegments, `${viewport.id}.json`);
  const axePath = path.join(output, "accessibility", scenario.id, ...browserSegments, `${viewport.id}.json`);
  await writeJson(domPath, dom);
  await writeJson(axePath, axe);

  const visual = await compareBaseline({
    root,
    output,
    scenario,
    viewport,
    currentScreenshot,
    baselineManifest,
    thresholds,
    allowMissingBaseline,
    browserName,
    baselineBrowser,
    browserScopedArtifacts,
  });
  const findings = buildFindings({ scenario, viewport, dom, axe, visual, allowMissingBaseline });
  const impactLevels = axe.violations.flatMap((item) => item.nodes.map(() => item.impact || "minor"));
  const summary = {
    id: viewport.id,
    category: viewport.category,
    width: viewport.width,
    height: viewport.height,
    status: findings.some((item) => ["P0", "P1"].includes(item.severity)) ? "FAIL" : findings.length ? "WARN" : "PASS",
    dom: {
      scrollWidth: dom.scrollWidth,
      viewportWidth: dom.viewportWidth,
      overflowCount: dom.horizontalOverflow ? 1 : 0,
      offscreenCount: dom.offscreenControls.length,
      assertionsPassed: dom.contractAssertions.filter((item) => item.passed).length,
      assertionsTotal: dom.contractAssertions.length,
    },
    accessibility: {
      violations: axe.violations.length,
      critical: impactLevels.filter((item) => item === "critical").length,
      serious: impactLevels.filter((item) => item === "serious").length,
      moderate: impactLevels.filter((item) => item === "moderate").length,
      manualSemanticReview: "REQUIRED",
    },
    visual,
    artifacts: {
      currentScreenshot: relative(root, currentScreenshot),
      fullScreenshot: relative(root, fullScreenshot),
      dom: relative(root, domPath),
      accessibility: relative(root, axePath),
    },
  };
  await context.close();
  return {
    summary,
    findings,
    currentScreenshot,
    baselineScreenshot: visual.baselinePath ? path.resolve(root, visual.baselinePath) : null,
  };
}


async function captureDom(page, scenario) {
  return page.evaluate((input) => {
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
    };
    const rectFor = (element) => {
      const rect = element.getBoundingClientRect();
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height, right: rect.right, bottom: rect.bottom };
    };
    const controls = [...document.querySelectorAll("button,a[href],input,select,textarea,[role=button]")]
      .filter(visible)
      .map((element) => ({
        tag: element.tagName.toLowerCase(),
        name: element.getAttribute("aria-label") || element.getAttribute("title") || element.textContent.trim(),
        enforceBounds: element.hasAttribute("data-qa-bounds"),
        rect: rectFor(element),
      }));
    const offscreenControls = controls.filter((item) => item.enforceBounds && (item.rect.x < 0 || item.rect.right > innerWidth || item.rect.y < 0 || item.rect.bottom > innerHeight));
    const assertions = (input.contractAssertions || []).map((assertion) => {
      const element = document.querySelector(assertion.selector);
      let passed = Boolean(element && visible(element));
      if (passed && assertion.type === "text") passed = element.textContent.includes(assertion.includes || "");
      if (passed && assertion.type === "attribute") passed = element.getAttribute(assertion.attribute) === assertion.value;
      return { id: assertion.id, selector: assertion.selector, type: assertion.type || "visible", passed };
    });
    return {
      title: document.title,
      headings: [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")].filter(visible).map((element) => ({ level: Number(element.tagName.slice(1)), text: element.textContent.trim() })),
      landmarks: [...document.querySelectorAll("header,nav,main,aside,footer,[role=banner],[role=navigation],[role=main],[role=complementary],[role=contentinfo]")].filter(visible).map((element) => element.getAttribute("role") || element.tagName.toLowerCase()),
      controls,
      offscreenControls,
      horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      viewportWidth: innerWidth,
      viewportHeight: innerHeight,
      contractAssertions: assertions,
    };
  }, { contractAssertions: scenario.contractAssertions || [] });
}


async function compareBaseline({ root, output, scenario, viewport, currentScreenshot, baselineManifest, thresholds, allowMissingBaseline, browserName, baselineBrowser, browserScopedArtifacts }) {
  const resolved = resolveBaselineEntry(baselineManifest, scenario.id, browserName, viewport.id, baselineBrowser);
  const entry = resolved.entry;
  if (!entry) {
    return {
      status: allowMissingBaseline ? "NOT_RUN" : "FAIL",
      governed: false,
      diffRatio: null,
      reason: `No governed ${browserName} baseline entry`,
      baselineSource: resolved.source,
    };
  }
  const baselinePath = path.resolve(root, entry.path);
  try {
    const actualHash = await sha256File(baselinePath);
    if (actualHash !== entry.sha256) {
      return { status: "FAIL", governed: false, diffRatio: null, reason: "Baseline hash does not match its approval manifest", baselinePath: entry.path };
    }
    const baseline = PNG.sync.read(await fs.readFile(baselinePath));
    const current = PNG.sync.read(await fs.readFile(currentScreenshot));
    if (baseline.width !== current.width || baseline.height !== current.height) {
      return { status: "FAIL", governed: true, diffRatio: 1, reason: "Baseline and current dimensions differ", baselinePath: entry.path };
    }
    const diff = new PNG({ width: baseline.width, height: baseline.height });
    const changed = pixelmatch(baseline.data, current.data, diff.data, baseline.width, baseline.height, {
      threshold: 0.1,
      includeAA: false,
    });
    const diffRatio = changed / (baseline.width * baseline.height);
    const diffPath = path.join(output, "diffs", scenario.id, ...(browserScopedArtifacts ? [browserName] : []), viewport.id, "diff.png");
    await fs.mkdir(path.dirname(diffPath), { recursive: true });
    await fs.writeFile(diffPath, PNG.sync.write(diff));
    return {
      status: diffRatio <= thresholds.maxPixelDiffRatio ? "PASS" : "FAIL",
      governed: true,
      diffRatio,
      maxDiffRatio: thresholds.maxPixelDiffRatio,
      baselinePath: entry.path,
      baselineSha256: actualHash,
      baselineSource: resolved.source,
      diffPath: relative(root, diffPath),
    };
  } catch (error) {
    return { status: "FAIL", governed: false, diffRatio: null, reason: error.message, baselinePath: entry.path };
  }
}


function buildFindings({ scenario, viewport, dom, axe, visual, allowMissingBaseline }) {
  const findings = [];
  if (dom.horizontalOverflow) {
    findings.push(finding(viewport, "dom-horizontal-overflow", "P1", "responsive", `scrollWidth ${dom.scrollWidth} exceeds viewportWidth ${dom.viewportWidth}`, true, "dom"));
  }
  if (dom.offscreenControls.length) {
    findings.push(finding(viewport, "dom-offscreen-control", "P1", "responsive", `${dom.offscreenControls.length} interactive control(s) extend outside the usable viewport`, true, "dom"));
  }
  for (const assertion of dom.contractAssertions.filter((item) => !item.passed)) {
    findings.push(finding(viewport, `contract-${assertion.id}`, "P1", "workflow", `Design contract assertion failed: ${assertion.id}`, false, "contract"));
  }
  for (const violation of axe.violations) {
    const severity = ["critical", "serious"].includes(violation.impact) ? "P1" : "P2";
    findings.push(finding(viewport, `axe-${violation.id}`, severity, "accessibility", `${violation.help} (${violation.nodes.length} node(s))`, severity === "P1", "axe"));
  }
  if (visual.status === "FAIL") {
    findings.push(finding(viewport, "visual-baseline-drift", "P1", "drift", visual.reason || `Pixel diff ratio ${visual.diffRatio} exceeds ${visual.maxDiffRatio}`, false, "pixelmatch"));
  } else if (visual.status === "NOT_RUN" && !allowMissingBaseline) {
    findings.push(finding(viewport, "visual-baseline-missing", "P1", "drift", "No governed baseline exists", false, "baseline-governance"));
  }
  return findings;
}


function finding(viewport, id, severity, rootCause, message, repairable, source) {
  return {
    id: `${id}:${viewport.id}`,
    viewport: viewport.id,
    viewportCategory: viewport.category,
    severity,
    rootCause,
    message,
    repairable,
    source,
    preserve: ["governed baseline", "design contract", "existing product authority"],
    change: repairable ? ["bounded deterministic source correction"] : ["human review required"],
  };
}


function summarize(viewports) {
  return {
    criticalAccessibilityViolations: sum(viewports, (item) => item.accessibility.critical),
    seriousAccessibilityViolations: sum(viewports, (item) => item.accessibility.serious),
    moderateAccessibilityViolations: sum(viewports, (item) => item.accessibility.moderate),
    containmentFailures: sum(viewports, (item) => item.dom.overflowCount + item.dom.offscreenCount),
    domAssertionsPassed: sum(viewports, (item) => item.dom.assertionsPassed),
    domAssertionsTotal: sum(viewports, (item) => item.dom.assertionsTotal),
    contractAssertionsPassed: sum(viewports, (item) => item.dom.assertionsPassed),
    contractAssertionsTotal: sum(viewports, (item) => item.dom.assertionsTotal),
  };
}


async function runInteractions(page, interactions) {
  for (const interaction of interactions) {
    const locator = page.locator(interaction.selector);
    if (interaction.action === "click") await locator.click();
    else if (interaction.action === "fill") await locator.fill(interaction.value || "");
    else if (interaction.action === "press") await locator.press(interaction.key);
    else throw new Error(`Unsupported interaction action: ${interaction.action}`);
  }
}


export async function startStaticServer(staticRoot) {
  const root = path.resolve(staticRoot);
  const server = http.createServer(async (request, response) => {
    try {
      const requestURL = new URL(request.url, "http://127.0.0.1");
      const pathname = requestURL.pathname === "/" ? "/index.html" : requestURL.pathname;
      const target = path.resolve(root, `.${pathname}`);
      if (target !== root && !target.startsWith(`${root}${path.sep}`)) {
        response.writeHead(403).end("Forbidden");
        return;
      }
      const content = await fs.readFile(target);
      response.writeHead(200, { "content-type": CONTENT_TYPES[path.extname(target)] || "application/octet-stream", "cache-control": "no-store" });
      response.end(content);
    } catch {
      response.writeHead(404).end("Not found");
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  return {
    baseURL: `http://127.0.0.1:${address.port}`,
    close: () => new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve()))),
  };
}


async function readJson(filePath, fallback) {
  try {
    return JSON.parse(await fs.readFile(filePath, "utf8"));
  } catch (error) {
    if (fallback !== undefined && error.code === "ENOENT") return fallback;
    throw error;
  }
}


async function writeJson(filePath, value) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}


async function sha256File(filePath) {
  const hash = crypto.createHash("sha256");
  hash.update(await fs.readFile(filePath));
  return hash.digest("hex");
}


function gitSha(root) {
  const result = spawnSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" });
  return result.status === 0 ? result.stdout.trim() : null;
}


function gitBranch(root) {
  const result = spawnSync("git", ["branch", "--show-current"], { cwd: root, encoding: "utf8" });
  return result.status === 0 ? result.stdout.trim() || null : null;
}


function relative(root, target) {
  return path.relative(root, target).split(path.sep).join("/");
}


function sum(items, selector) {
  return items.reduce((total, item) => total + Number(selector(item) || 0), 0);
}


export const modulePath = fileURLToPath(import.meta.url);
