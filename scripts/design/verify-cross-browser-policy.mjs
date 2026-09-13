#!/usr/bin/env node
import assert from "node:assert/strict";

import { normalizeBrowserPolicy, resolveBaselineEntry } from "./visual-qa-lib.mjs";


const policy = normalizeBrowserPolicy({
  browserPolicy: { required: ["chromium", "firefox", "webkit"], baselineBrowser: "chromium" },
});
assert.deepEqual(policy.browsers, ["chromium", "firefox", "webkit"]);
assert.equal(policy.baselineBrowser, "chromium");

const manifest = {
  scenarios: {
    surface: {
      viewports: { desktop: { path: "legacy.png", sha256: "a".repeat(64) } },
      browsers: {
        firefox: { viewports: { desktop: { path: "firefox.png", sha256: "b".repeat(64) } } },
      },
    },
  },
};
assert.equal(resolveBaselineEntry(manifest, "surface", "chromium", "desktop", "chromium").entry.path, "legacy.png");
assert.equal(resolveBaselineEntry(manifest, "surface", "firefox", "desktop", "chromium").entry.path, "firefox.png");
assert.equal(resolveBaselineEntry(manifest, "surface", "webkit", "desktop", "chromium").entry, null);
assert.throws(() => normalizeBrowserPolicy({}, ["netscape"]), /Unsupported browser/);

console.log("Cross-browser policy: PASS (three engines; browser-scoped baseline isolation verified)");
