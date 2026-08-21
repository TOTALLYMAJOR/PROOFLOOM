#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

import { runScenario } from "./visual-qa-lib.mjs";


const repositoryRoot = process.cwd();
const sourceSurface = path.join(repositoryRoot, "tests/fixtures/visual-surface");
const baseScenario = JSON.parse(await fs.readFile(path.join(repositoryRoot, "tests/design/scenarios/design-department-surface.json"), "utf8"));
const baselineManifest = path.join(repositoryRoot, ".design/baselines/manifest.json");
const baselineHashBefore = await sha256File(baselineManifest);
const outputRoot = path.join(repositoryRoot, "artifacts/design/evidence/repair-cycles");

const cases = [
  {
    id: "overflow",
    file: "surface.css",
    clean: "  width: min(100%, 1440px);",
    fault: "  width: 760px;",
    findingId: "dom-horizontal-overflow:mobile-390x844",
  },
  {
    id: "offscreen-primary-action",
    file: "surface.css",
    clean: "  width: 100%;\n  min-height: 48px;",
    fault: "  transform: translateX(120vw);\n  width: 100%;\n  min-height: 48px;",
    findingId: "dom-offscreen-control:mobile-390x844",
  },
  {
    id: "accessible-name",
    file: "index.html",
    clean: "        <button class=\"primary-action\" type=\"button\" data-qa-primary data-qa-bounds aria-expanded=\"false\" aria-controls=\"evidence-details\">\n          Inspect latest evidence\n        </button>",
    fault: "        <button class=\"primary-action\" type=\"button\" data-qa-primary data-qa-bounds aria-expanded=\"false\" aria-controls=\"evidence-details\">\n          <span aria-hidden=\"true\">+</span>\n        </button>",
    repair: "        <button class=\"primary-action\" type=\"button\" data-qa-primary data-qa-bounds aria-label=\"Inspect latest evidence\" aria-expanded=\"false\" aria-controls=\"evidence-details\">\n          <span aria-hidden=\"true\">+</span>\n        </button>",
    findingId: "axe-button-name:mobile-390x844",
  },
];

const summary = [];
for (const repairCase of cases) {
  summary.push(await proveRepair(repairCase));
}

const baselineHashAfter = await sha256File(baselineManifest);
if (baselineHashBefore !== baselineHashAfter) {
  throw new Error("Repair proof mutated the governed baseline manifest");
}
console.log(JSON.stringify({ status: "PASS", cycles: summary, baselineManifestUnchanged: true }, null, 2));


async function proveRepair(repairCase) {
  const temporaryRoot = await fs.mkdtemp(path.join(os.tmpdir(), `design-intelligence-${repairCase.id}-`));
  const surfaceRoot = path.join(temporaryRoot, "surface");
  try {
    await fs.cp(sourceSurface, surfaceRoot, { recursive: true });
    const target = path.join(surfaceRoot, repairCase.file);
    const source = await fs.readFile(target, "utf8");
    if (source.split(repairCase.clean).length !== 2) {
      throw new Error(`Failure injection source must match exactly once for ${repairCase.id}`);
    }
    await fs.writeFile(target, source.replace(repairCase.clean, repairCase.fault), "utf8");

    const scenario = {
      ...baseScenario,
      id: `repair-cycle-${repairCase.id}`,
      surface: `Repair cycle: ${repairCase.id}`,
      staticRoot: surfaceRoot,
      viewports: [{ id: "mobile-390x844", category: "mobile", width: 390, height: 844 }],
      repairIterations: 1,
    };
    const scenarioPath = path.join(temporaryRoot, "scenario.json");
    await writeJson(scenarioPath, scenario);
    const beforeOutput = path.join(temporaryRoot, "before");
    const before = await runScenario({
      scenarioPath,
      repositoryRoot,
      outputRoot: beforeOutput,
      allowMissingBaseline: true,
    });
    const detected = before.report.findings.find((item) => item.id === repairCase.findingId);
    if (before.report.status !== "FAIL" || !detected) {
      throw new Error(`${repairCase.id} did not produce expected finding ${repairCase.findingId}`);
    }

    const plan = {
      id: `RP-DEMO-${repairCase.id.toUpperCase()}`,
      taskId: "ADD-V2-DEMO",
      authority: "visual-only",
      architectureImpact: false,
      iterationLimit: 3,
      allowedFiles: [repairCase.file],
      repairs: [{
        findingId: repairCase.findingId,
        severity: detected.severity,
        file: repairCase.file,
        expected: repairCase.fault,
        replacement: repairCase.repair || repairCase.clean,
        evidenceId: repairCase.findingId,
      }],
    };
    const planPath = path.join(temporaryRoot, "repair-plan.json");
    const evidencePath = path.join(temporaryRoot, "repair-evidence.json");
    await writeJson(planPath, plan);
    await writeJson(evidencePath, { findings: before.report.findings });
    const repair = spawnSync(
      process.env.DESIGN_INTELLIGENCE_PYTHON || "python3",
      ["-m", "design_intelligence.cli", "repair", "--root", surfaceRoot, "--plan", planPath, "--evidence", evidencePath, "--iteration", "1", "--apply", "--format", "json"],
      { cwd: repositoryRoot, encoding: "utf8" },
    );
    if (repair.status !== 0) {
      throw new Error(`Repair command failed for ${repairCase.id}: ${repair.stderr || repair.stdout}`);
    }
    const repairResult = JSON.parse(repair.stdout);
    const afterOutput = path.join(temporaryRoot, "after");
    const after = await runScenario({
      scenarioPath,
      repositoryRoot,
      outputRoot: afterOutput,
      allowMissingBaseline: true,
    });
    if (after.report.status !== "PASS") {
      throw new Error(`${repairCase.id} did not pass after repair: ${JSON.stringify(after.report.findings)}`);
    }

    const evidenceRoot = path.join(outputRoot, repairCase.id);
    await fs.mkdir(evidenceRoot, { recursive: true });
    const beforeScreenshot = path.join(beforeOutput, "screenshots", scenario.id, "mobile-390x844", "current.png");
    const afterScreenshot = path.join(afterOutput, "screenshots", scenario.id, "mobile-390x844", "current.png");
    await copyEvidenceImage(beforeScreenshot, path.join(evidenceRoot, "before.png"));
    await copyEvidenceImage(afterScreenshot, path.join(evidenceRoot, "after.png"));
    const evidence = {
      schemaVersion: 1,
      id: `repair-cycle-${repairCase.id}`,
      findingId: repairCase.findingId,
      beforeStatus: before.report.status,
      repairStatus: repairResult.status,
      afterStatus: after.report.status,
      iteration: repairResult.iteration,
      maxIterations: repairResult.max_iterations,
      changedFiles: repairResult.changed_files,
      beforeHash: repairResult.before_hashes[repairCase.file],
      afterHash: repairResult.after_hashes[repairCase.file],
      beforeScreenshot: `artifacts/design/evidence/repair-cycles/${repairCase.id}/before.png`,
      afterScreenshot: `artifacts/design/evidence/repair-cycles/${repairCase.id}/after.png`,
      baselineManifestSha256: baselineHashBefore,
      authorityBoundary: "visual-only",
    };
    await writeJson(path.join(evidenceRoot, "evidence.json"), evidence);
    return { id: evidence.id, status: "PASS", findingId: repairCase.findingId };
  } finally {
    await fs.rm(temporaryRoot, { recursive: true, force: true });
  }
}


async function writeJson(filePath, value) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}


async function copyEvidenceImage(source, destination) {
  await fs.copyFile(source, destination);
  await fs.chmod(destination, 0o644);
  const mode = (await fs.stat(destination)).mode & 0o777;
  if (mode !== 0o644) {
    throw new Error(`Evidence image permissions must be 0644: ${destination}`);
  }
}


async function sha256File(filePath) {
  const hash = crypto.createHash("sha256");
  hash.update(await fs.readFile(filePath));
  return hash.digest("hex");
}
