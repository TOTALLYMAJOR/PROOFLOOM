# Design Adoption Gate

## Purpose

The Design Adoption Gate turns a site, screenshot, or design document into bounded implementation guidance without allowing the reference or analyzer to become product authority.

```text
task + site/images
  -> repository authority discovery
  -> current design-system health audit
  -> scoped institutional-memory retrieval (max 20 records; required for product profiles)
  -> replay-audited human governance receipts
  -> hash-bound human/model observations
  -> deterministic ADOPT / ADAPT / DEFER / DECLINE / BLOCKED
  -> existing design contract
  -> existing implementation, Playwright QA, quality, repair, and memory cycle
```

The package does not add a second backlog, component library, token system, E2E hierarchy, quality model, baseline store, or memory database.

## Authority And Evidence

Authority order remains: current user requirement, repository governance, product requirements/backlog, architecture/design decisions, current tokens/components, institutional memory, external reference, analyzer recommendation, general convention.

Three properties are deliberately separate:

- **Authority:** whether a source may constrain a change.
- **Validity:** whether its repository-bound bytes and schema are intact now.
- **Freshness:** whether accepted premises, exceptions, outcomes, and debt still apply to the requested scope.

URLs require captured DOM/screenshot artifacts with SHA-256 bindings. Local images are bound directly. A human or model adapter describes patterns using `reference-analysis.schema.json`; the deterministic engine ignores `recommendedDecision` and owns the final classification.

A `VERIFIED` product-capability claim is accepted only when at least one repository-relative evidence file matches its declared hash. `ABSENT` additionally requires `evidenceMethod: repository-search` and a structured hash-bound search receipt. A bare absence claim becomes `UNRESOLVED`, which forces `DEFER` unless a protected risk independently requires `DECLINE`.

Named product profiles require configured institutional memory. A missing memory authority returns `REVIEW_REQUIRED`; it does not silently erase prior decisions, exceptions, rejected outcomes, or debt. Profiles under an active human governance boundary may also require a replay-audited baseline review receipt. `DEFER` becomes `HELD`, `REJECT` blocks, and only an active audited approval clears that supplied constraint.

## Design-System Health

The audit reports `HEALTHY`, `NEEDS_ALIGNMENT`, `CONFLICTED`, or `INSUFFICIENT_EVIDENCE`. It evaluates canonical design documentation, tokens, component authority, frontend/accessibility tooling, and semantic duplicates. Hyphen- and underscore-named design systems are recognized; design principles and design contracts remain distinct complementary authority roles instead of being mislabeled as competing systems. The presence of a component folder or CSS variable does not by itself mean the system is healthy.

A conflicted system cannot authorize component, workflow, or visual extension. The gate returns `DEFER` until competing authorities are converged. It does not auto-migrate the repository.

## Decision Rules

- `ADOPT`: evidence-bound visual/interaction principle fits current product capability and authority.
- `ADAPT`: the transferable pattern is useful, but source identity or component/workflow expression must be translated through existing tokens and primitives.
- `DEFER`: capability, memory freshness/debt, or design-system authority is unresolved.
- `DECLINE`: required capability is absent or adoption would introduce a protected product risk.
- `BLOCKED`: repository instructions, accepted backlog/requirements, architecture, evidence integrity, or protected memory rules prohibit the change.

Only a report whose overall status is `READY` can unlock a reference-backed mission. The generated contract contains only `ADOPT` and `ADAPT` patterns.

## Operator Workflow

Capture a site without granting semantic authority:

```bash
npm run design:reference:capture -- \
  --url https://example.com/reference \
  --output artifacts/design/references/example
```

Create `reference-analysis.json` using the schema and include the capture's `sourceEvidence`. Then evaluate and save:

```bash
design-intelligence adopt "Improve the proposal workspace" \
  --reference https://example.com/reference \
  --analysis artifacts/design/references/example/reference-analysis.json \
  --profile quotepilot \
  --surface ProposalWorkspace \
  --governance-receipt /path/to/governed-review-receipt.json \
  --save --strict --format json
```

Audit before implementation:

```bash
design-intelligence adoption-audit --root . \
  --input artifacts/design/adoptions/improve-the-proposal-workspace/adoption-report.json
```

Attach the report to the normal mission:

```bash
design-intelligence "Improve the proposal workspace" \
  --reference https://example.com/reference \
  --direction recommended \
  --adoption-report artifacts/design/adoptions/improve-the-proposal-workspace/adoption-report.json \
  --save
```

For a local image, replace `--reference <url>` with `--image <repository-relative-path>` in both `adopt` and the mission command. The image bytes are hash-bound directly and do not require the Playwright capture step.

## Failure Boundaries

The gate never mutates implementation, applies repair, changes quality thresholds, or promotes baselines. Governance receipts are inputs to authorization, not permissions manufactured by the gate. Existing repair remains exact, evidence-linked, allowlisted, visual-only, and capped at three iterations. Existing baseline promotion remains human approval-bound. Any architecture, backend, authority, evidence-integrity, memory-availability, or scope crossing stops automatic continuation.

The semantic analyzer is an adapter boundary. This repository ships deterministic contracts and Playwright capture, not a mandatory model vendor or hidden model call. Human-reviewed analysis and model-produced analysis use the same schema and receive the same deterministic enforcement.
