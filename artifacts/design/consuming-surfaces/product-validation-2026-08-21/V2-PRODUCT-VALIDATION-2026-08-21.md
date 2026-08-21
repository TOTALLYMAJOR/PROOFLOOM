# V2 Product Validation: QuietPilot and QuotePilot

Date: August 21, 2026

## Authority Boundary

Both product repositories were exercised read-only. No product source,
governance, threshold, test, or baseline file was changed. Product acceptance,
manual semantic accessibility review, and baseline promotion remain human gates.

## QuietPilot

- repository: `/home/administrator/QP/QuietPilot`
- branch: `feat/ux029-od6-closeout`
- commit: `874cf1db786c50a437653cae0d17e2f6b58641b0`
- surface: `/landing`, canonical Obsidian public landing
- deterministic browser status: PASS
- viewports: 5/5 rendered
- DOM assertions: 25/25
- contract assertions: 25/25
- containment failures: 0
- critical, serious, or moderate Axe nodes: 0
- governed pixel evidence: NOT_RUN, because no approved product baseline exists
- deterministic quality: 80/100 FAIL, because baseline and visual-threshold gates remain closed
- model review: WARN P2 for unusually subdued secondary evidence salience

The first navigation reached the unchanged 30-second timeout while Next.js
compiled 2,180 landing modules in 27.2 seconds. A direct route request then
returned HTTP 200, and the warm five-viewport run completed. This is recorded as
a local cold-start limitation, not a product QA defect.

## QuotePilot

- repository: `/home/administrator/projects_new/quoteflow`
- branch: `feature/landing-document-hero`
- commit: `c0b213f2e728365c66a272d3d0277c46ce51d3e7`
- surface: `/`, current document-hero public landing
- deterministic browser status: FAIL
- viewports: 5/5 rendered
- DOM assertions: 25/25
- contract assertions: 25/25
- containment failures: 0
- critical Axe nodes: 0
- serious Axe nodes: 30, six color-contrast nodes at each viewport
- governed pixel evidence: NOT_RUN, because no approved product baseline exists
- deterministic quality: 55/100 FAIL
- repair: not attempted; the user hold remains authoritative

## V2 Learning

The external runs exposed a quality-scorer defect when `diffRatio` was `null`
for an intentionally unbaselined viewport. V2 now treats missing pixel evidence
as unscored, leaves baseline gates closed, awards no visual points, and records
an explicit evidence note instead of crashing or fabricating zero-drift proof.
A regression test covers five unbaselined viewports.

## Reproduction

```bash
node scripts/design/visual-qa.mjs \
  --scenario examples/scenarios/quietpilot-landing.json \
  --output artifacts/design/consuming-surfaces/quietpilot \
  --base-url http://127.0.0.1:4327 \
  --source-root /home/administrator/QP/QuietPilot \
  --allow-missing-baseline

node scripts/design/visual-qa.mjs \
  --scenario examples/scenarios/quotepilot-landing-v2.json \
  --output artifacts/design/consuming-surfaces/quotepilot \
  --base-url http://127.0.0.1:4317 \
  --source-root /home/administrator/projects_new/quoteflow \
  --allow-missing-baseline
```

The QuotePilot command is expected to exit non-zero while its contrast debt and
repair hold remain active.
