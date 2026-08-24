# Design Adoption Gate Implementation Report

Date: 2026-08-23
Branch: `codex/design-adoption-gate-v4`
Status: implemented and locally verified

## Outcome

Design Intelligence now accepts reference sites and local images as evidence, audits the repository's current design-system health and authority sources, retrieves bounded institutional memory, and deterministically classifies observed patterns as `ADOPT`, `ADAPT`, `DEFER`, `DECLINE`, or `BLOCKED`.

Reference-backed implementation remains blocked until both conditions hold:

1. A design direction is explicitly selected.
2. A matching append-only adoption report replays as `READY` with intact source and repository-authority hashes.

For named product profiles, institutional memory must also be available. QuotePilot additionally requires a replay-audited human governance receipt: its existing `DEFER` receipt now produces `HELD` and cannot be bypassed by direction selection or a legacy report.

The report compiles permitted patterns into the existing design-contract format. No second backlog, token system, component system, E2E hierarchy, memory store, quality model, repair engine, or baseline authority was introduced.

## Changed Files

Core and workflow:

- `design_intelligence/adoption.py`
- `design_intelligence/cli.py`
- `design_intelligence/memory.py`
- `design_intelligence/missions.py`
- `design_intelligence/models.py`
- `design_intelligence/repository.py`
- `design_intelligence/self_audit.py`
- `design_intelligence/workflows.py`
- `scripts/design/capture-reference.mjs`
- `scripts/design/ci.py`
- `package.json`

Schemas and governance:

- `design_intelligence/data/schemas/reference-analysis.schema.json`
- `design_intelligence/data/schemas/design-adoption-report.schema.json`
- `design_intelligence/data/product_profiles/quotepilot.json`
- `.design/memory/schemas/reference-analysis.schema.json`
- `.design/memory/schemas/design-adoption-report.schema.json`

Skills and documentation:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/design/DESIGN-ADOPTION-GATE.md`
- `docs/IMPLEMENTATION-REPORT-DESIGN-ADOPTION-GATE.md`
- `skills/design-language/SKILL.md`
- `skills/design-language/references/mission-workflow.md`
- `skills/reference-intelligence/SKILL.md`
- `skills/reference-intelligence/references/reference-analysis.md`

Tests:

- `tests/test_adoption_gate.py`
- `tests/test_memory_v2.py`
- `tests/test_workflows.py`

Generated bounded evidence:

- `artifacts/design/references/design-department-surface/capture.json`
- `artifacts/design/references/design-department-surface/source-evidence.json`
- `artifacts/design/references/design-department-surface/page.html`
- `artifacts/design/references/design-department-surface/reference.png`
- `artifacts/design/references/design-department-surface/reference-analysis.json`
- `artifacts/design/adoptions/preserve-evidence-first-design-qa-hierarchy-v4/adoption-report.json`
- `artifacts/design/adoptions/preserve-evidence-first-design-qa-hierarchy-v4/authority-map.json`
- `artifacts/design/adoptions/preserve-evidence-first-design-qa-hierarchy-v4/design-system-health.json`
- `artifacts/design/adoptions/preserve-evidence-first-design-qa-hierarchy-v4/reference-analysis.json`
- `artifacts/design/adoptions/preserve-evidence-first-design-qa-hierarchy-v4/design-contract.json`

Generated QuoteFlow pilot evidence:

- `.design/memory/product-rules.json` with five hash-bound canonical authorities and ten indexed product rules
- `.design/memory/component-registry.json` with 101 deterministically scanned components
- `artifacts/design/adoptions/quotepilot-workspace-pilot-v4/adoption-report.json`
- `artifacts/design/adoptions/quotepilot-workspace-pilot-v4/authority-map.json`
- `artifacts/design/adoptions/quotepilot-workspace-pilot-v4/design-system-health.json`
- `artifacts/design/adoptions/quotepilot-workspace-pilot-v4/reference-analysis.json`

## Verification

Executed commands:

```bash
PYTHONPYCACHEPREFIX=/tmp/design-intelligence-pyc python3 -m compileall -q design_intelligence repo_fit tests
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
npm run design:reference:capture -- --url http://127.0.0.1:8123/ --output artifacts/design/references/design-department-surface
python3 -m design_intelligence.cli adopt "Preserve evidence-first Design QA hierarchy" --root . --reference http://127.0.0.1:8123/ --analysis artifacts/design/references/design-department-surface/reference-analysis.json --surface "Design QA Control Deck fixture" --save --strict
python3 -m design_intelligence.cli adoption-audit --root . --input artifacts/design/adoptions/preserve-evidence-first-design-qa-hierarchy-v4/adoption-report.json
npm run design:ci:quick
npm run design:ci:standard
npm run design:ci:full
git diff --check
sha256sum .design/baselines/manifest.json
```

Verified results:

- Python tests: 87 passed.
- Adoption report: `DAR-F501B946828B8852`, replay `PASS`, one source and seven repository authorities checked.
- QuotePilot pilot v4: `DAR-CB29DC358A4353FE`, replay `PASS`, 32 authorities checked, memory `AVAILABLE/PASS`, governance `HELD`, implementation not ready, and no contract emitted.
- Legacy reports remain `LEGACY_BLOCKED`; current-schema reports whose authority hashes drift are `HISTORICAL_BLOCKED` only when an exact-scope replacement replays successfully.
- Index-only memory verifies canonical source paths and SHA-256 hashes; source drift blocks adoption, and `--memory-only` setup installs no quality or baseline infrastructure.
- Bare `ABSENT` capability claims downgrade to `UNRESOLVED`; only structured hash-bound `repository-search` evidence preserves absence.
- `DESIGN_SYSTEM.md`, `DESIGN_PRINCIPLES.md`, and `DESIGN-CONTRACT.md` are detected as complementary authority roles rather than a fabricated dual system.
- Pattern decisions: one `ADOPT`, one identity-bounded `ADAPT`.
- Existing surface QA: five governed viewports passed.
- Deterministic quality: 100/100; drift 0.
- Accessibility: zero critical and zero serious automated findings.
- DOM/state and contract assertions: 25/25 each.
- Failure injection: malformed schema/report, source tamper, authority tamper, path escape, absent/unproven capability, design-system conflict/alignment, proposed-memory overreach, and model recommendation overreach covered.
- Bounded repair: overflow, off-screen primary action, and accessible-name cycles each failed before, repaired once, and passed after.
- Dependency audit: zero vulnerabilities.
- V1 skills: all five validators passed and skill identities remain intact.
- Baseline manifest remained `03346893f7b9dff8fdd01de647908fb581af1a943ca258ac428057bca65aeef1`.

## Limitations

- Semantic visual interpretation is an explicit human/model adapter boundary. The package does not silently call a model or pretend deterministic code can judge aesthetics.
- Playwright site capture handles public or already-accessible URLs. Authenticated references require the consuming repository to provide an authorized capture flow without committing credentials.
- Repository statement reconciliation is bounded lexical/structured enforcement, not a general natural-language theorem prover. Ambiguous conflicts return review rather than automatic permission.
- Cross-repository governance receipt descriptors retain the canonical authority root as an absolute path. Cross-machine verification requires a governed evidence export or trusted-root remapping; failure to resolve the authority root blocks replay.
- Automated axe passing does not replace manual semantic accessibility review.
- The bounded proof is local repository evidence for the Design QA Control Deck fixture. It is not production deployment, customer acceptance, or product-owner aesthetic approval.

## Next V3 Opportunities

- Add a pluggable semantic-analysis adapter runner that validates model output against the existing schema without granting it decision authority.
- Add protected CI artifact signing or identity-provider receipts for cross-machine adoption-report trust.
- Add authenticated capture adapters that reuse consuming-repository browser sessions without storing secrets.
- Add richer premise-expiration links from adoption pattern IDs to accepted decisions and measured outcomes.
- Add PR annotations that summarize `ADOPT`/`ADAPT`/`DEFER`/`DECLINE` without granting merge, repair, or baseline authority.
