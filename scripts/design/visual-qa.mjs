#!/usr/bin/env node
import path from "node:path";

import { runCrossBrowserScenario, runScenario } from "./visual-qa-lib.mjs";


const args = parseArgs(process.argv.slice(2));
if (!args.scenario) {
  console.error("Usage: visual-qa.mjs --scenario <file> [--browser chromium|firefox|webkit|all] [--output <dir>] [--base-url <url>] [--source-root <dir>] [--allow-missing-baseline]");
  process.exit(2);
}

try {
  const browsers = args.browsers || [];
  const shared = {
    scenarioPath: args.scenario,
    repositoryRoot: process.cwd(),
    sourceRoot: args.sourceRoot,
    outputRoot: args.output,
    baseURL: args.baseUrl,
    allowMissingBaseline: args.allowMissingBaseline,
  };
  const result = browsers.length > 1 || browsers.includes("all")
    ? await runCrossBrowserScenario({ ...shared, browsers })
    : await runScenario({ ...shared, browserName: browsers[0] || "chromium" });
  console.log(JSON.stringify({
    status: result.report.status,
    report: path.relative(process.cwd(), result.reportPath),
    reviewManifest: result.reviewPath ? path.relative(process.cwd(), result.reviewPath) : undefined,
  }, null, 2));
  process.exit(result.report.status === "PASS" ? 0 : 1);
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}


function parseArgs(values) {
  const parsed = {};
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    if (value === "--scenario") parsed.scenario = values[++index];
    else if (value === "--output") parsed.output = values[++index];
    else if (value === "--base-url") parsed.baseUrl = values[++index];
    else if (value === "--source-root") parsed.sourceRoot = values[++index];
    else if (value === "--allow-missing-baseline") parsed.allowMissingBaseline = true;
    else if (value === "--browser") (parsed.browsers ||= []).push(values[++index]);
    else throw new Error(`Unknown argument: ${value}`);
  }
  return parsed;
}
