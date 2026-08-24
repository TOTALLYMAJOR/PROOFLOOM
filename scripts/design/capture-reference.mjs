#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright";


const args = parseArgs(process.argv.slice(2));
if (!args.url || !args.output) {
  console.error("Usage: capture-reference.mjs --url <url> --output <repository-relative-dir> [--width 1440] [--height 1000]");
  process.exit(2);
}

const root = process.cwd();
const output = path.resolve(root, args.output);
if (path.relative(root, output).startsWith("..") || path.isAbsolute(path.relative(root, output))) {
  throw new Error("Reference capture output must remain inside the repository");
}

const browser = await chromium.launch({ headless: true });
try {
  const viewport = {
    width: positiveInteger(args.width, 1440),
    height: positiveInteger(args.height, 1000),
  };
  const context = await browser.newContext({ viewport, reducedMotion: "reduce" });
  const page = await context.newPage();
  await page.goto(args.url, { waitUntil: "domcontentloaded", timeout: 30_000 });
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}" });
  await page.waitForTimeout(250);

  await fs.mkdir(output, { recursive: true });
  const screenshotPath = path.join(output, "reference.png");
  const domPath = path.join(output, "page.html");
  await page.screenshot({ path: screenshotPath, fullPage: true, animations: "disabled" });
  await fs.writeFile(domPath, await page.content(), "utf8");

  const artifacts = await Promise.all([
    artifact(root, screenshotPath, "screenshot"),
    artifact(root, domPath, "dom-capture"),
  ]);
  const capturedAt = new Date().toISOString();
  const metadata = {
    schemaVersion: 1,
    source: args.url,
    capturedAt,
    finalUrl: page.url(),
    title: await page.title(),
    viewport,
    artifacts,
    authority: "Captured bytes are evidence only; a human or model adapter must describe patterns.",
  };
  const evidence = {
    schemaVersion: 1,
    sourceEvidence: [{ source: args.url, artifacts }],
  };
  const metadataPath = path.join(output, "capture.json");
  const evidencePath = path.join(output, "source-evidence.json");
  await writeJson(metadataPath, metadata);
  await writeJson(evidencePath, evidence);
  console.log(JSON.stringify({
    status: "CAPTURED",
    capture: path.relative(root, metadataPath),
    sourceEvidence: path.relative(root, evidencePath),
    artifacts,
  }, null, 2));
} finally {
  await browser.close();
}


function parseArgs(values) {
  const parsed = {};
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    if (value === "--url") parsed.url = values[++index];
    else if (value === "--output") parsed.output = values[++index];
    else if (value === "--width") parsed.width = values[++index];
    else if (value === "--height") parsed.height = values[++index];
    else throw new Error(`Unknown argument: ${value}`);
  }
  return parsed;
}


function positiveInteger(value, fallback) {
  const parsed = Number.parseInt(value ?? fallback, 10);
  if (!Number.isInteger(parsed) || parsed <= 0) throw new Error("Viewport dimensions must be positive integers");
  return parsed;
}


async function artifact(root, filePath, kind) {
  const content = await fs.readFile(filePath);
  return {
    kind,
    path: path.relative(root, filePath).split(path.sep).join("/"),
    sha256: crypto.createHash("sha256").update(content).digest("hex"),
  };
}


async function writeJson(filePath, value) {
  await fs.writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}
