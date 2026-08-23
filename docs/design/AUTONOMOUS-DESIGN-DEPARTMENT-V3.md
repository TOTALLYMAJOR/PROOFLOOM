# Autonomous Design Department V3

## Status

V3 is implemented on top of the V2 foundation. Slice 0 established remote execution and baseline review requests. Slice 1 added append-only human decision receipts and lifecycle/preflight governance. Slice 2 adds the plain-English mission front door, surface-specific direction reasoning, reference ledger, explicit direction selection, and rendered-proof gate.

## Slice 2: one-command design missions

Run from a consuming repository:

```bash
design-intelligence "Improve the proposal comparison flow"
```

The command is read-only and:

- inspects repository authorities and existing evidence
- infers `marketing`, `app-workflow`, `customer-proposal`, `mobile`, or `general` mode
- presents three product-fit design directions and recommends one
- blocks implementation until a direction is explicitly selected
- marks supplied references as `RESEARCH_REQUIRED` until their patterns and transformations are recorded
- defines surface-specific rendered proof using the repository's existing browser hierarchy

An explicit selection can be made with `--direction recommended` or a direction ID. `--save` writes a predictable generated bundle under `artifacts/design/missions/<task>/`; default startup remains read-only. The mission bundle is evidence and handoff material, not a new repository authority.

## Slice 0 objective

Turn a completed visual-QA run into a hash-bound review request without granting an agent authority to approve or mutate a baseline.

The workflow is:

> Product evidence -> deterministic QA -> model review -> candidate hash binding -> human review -> existing governed promotion path

The five V1 skills, V2 memory, quality scoring, repair boundaries, and baseline promotion path remain canonical. V3 extends those authorities rather than creating parallel infrastructure.

## Baseline review requests

Create a request:

```bash
python3 -m design_intelligence.cli baseline request \
  --root . \
  --scenario product-surface \
  --product Product \
  --qa-report artifacts/design/reports/product-surface/qa-report.json \
  --model-review artifacts/design/reports/product-surface/model-visual-review.json \
  --candidate-root artifacts/design/screenshots/product-surface \
  --requested-by agent:codex \
  --output artifacts/design/baseline-requests/product-surface.json \
  --format json
```

Audit the bound files later:

```bash
python3 -m design_intelligence.cli baseline request-audit \
  --root . \
  --input artifacts/design/baseline-requests/product-surface.json \
  --format json
```

A request is `REVIEWABLE` only when all of the following are true:

- deterministic QA reports `PASS`
- source revision includes a commit SHA
- critical and serious accessibility counts are zero
- containment, DOM/state, and design-contract assertions pass completely
- every configured viewport has a candidate screenshot
- model review is `PASS` or `WARN`

A model `WARN` never becomes automatic aesthetic approval. It preserves the finding for product-owner review. A model `FAIL`, failed deterministic gate, missing candidate, or insufficient coverage makes the request `BLOCKED`.

Each request binds:

- QA report path, SHA-256, and status
- model-review path, SHA-256, verdict, and severity
- source repository, branch, and commit
- every viewport candidate path and SHA-256
- deterministic request identity derived from source revision and candidates
- blockers and required human approvals

Request creation sets `baselineMutationPerformed: false` and `promotionAuthority: human-required`. It does not call `baseline promote`, write the baseline manifest, accept a design-memory decision, or apply a repair.

## Remote CI

`.github/workflows/design-ci.yml` runs with read-only repository permissions:

- pull requests run `quick`, then `standard`
- pushes to `main` run `quick`, `standard`, then `full`
- manual dispatch can run all three tiers
- standard and full upload bounded evidence artifacts for 14 days
- no remote job promotes baselines or invokes `repair --apply`

The full tier proves repairs only against the existing isolated fixture workflow. Product repair remains subject to product scope, authority, and the three-iteration limit.

## Product pilot decisions

QuietPilot and QuotePilot are evidence pilots, not baseline promotions:

- QuietPilot may produce a `REVIEWABLE` request when its five-viewport PASS evidence and P2 model warning remain hash-valid. Human visual and semantic review are still required.
- QuotePilot must produce a `BLOCKED` request while its five-viewport evidence contains serious contrast violations and the explicit product repair hold remains active.

Neither product repository is modified by request creation.

## Slice 0 local proof - 2026-08-21

- QuietPilot request `BR-0ABFCCDDFB7A4A62`: `REVIEWABLE`, five candidates, QA `PASS`, model `WARN/P2`, and no baseline mutation.
- QuotePilot request `BR-9C2D4593B699634F`: `BLOCKED`, five candidates, QA `FAIL`, model `FAIL/P1`, 30 serious accessibility violations, and no baseline mutation or repair.
- Both request audits passed with seven evidence hashes checked per request.
- The governed baseline manifest SHA-256 remained `03346893f7b9dff8fdd01de647908fb581af1a943ca258ac428057bca65aeef1` before and after request creation and all three repair proofs.
- The local full tier passed 32 tests, five-viewport fixture QA, quality 100/100, drift 0, three deterministic repair cycles, five V1 skill validators, dependency audit, and self-audit.

Local proof does not equal product-owner visual acceptance, production deployment, or baseline approval.

## Slice 1: review decisions and lifecycle

Record a human decision from an explicit input file:

```bash
python3 -m design_intelligence.cli baseline decide \
  --root . \
  --request artifacts/design/baseline-requests/product-surface.json \
  --decision artifacts/design/human-review/product-surface-decision.json \
  --output artifacts/design/baseline-decisions/product-surface-decision.json \
  --format json
```

Receipt decisions are deliberately asymmetric:

- `APPROVE` requires a non-stale `REVIEWABLE` request, explicit `human:` authority, accepted design-memory decision, hash-bound visual acceptance, hash-bound semantic accessibility acceptance, and a validity window no longer than seven days.
- `DEFER` may preserve a blocked request without fabricating acceptance. It requires human authority and a future `reviewAfter` date, but grants no promotion authority.
- `REJECT` records a final human decision without requiring acceptance evidence and grants no promotion authority.

Every receipt is append-only, binds the request SHA-256, records `baselineMutationPerformed: false` and `promotionPerformed: false`, and may supersede only an earlier receipt for the same request. A later valid receipt invalidates preflight from the superseded approval.

Lifecycle evaluation is non-mutating:

```bash
python3 -m design_intelligence.cli baseline receipt-audit --root . --input review-receipt.json
python3 -m design_intelligence.cli baseline lifecycle --root .
python3 -m design_intelligence.cli baseline preflight --root . --receipt review-receipt.json
```

Lifecycle states include `REVIEWABLE`, `BLOCKED`, `STALE`, `SUPERSEDED`, `APPROVED_PENDING_PROMOTION`, `APPROVAL_EXPIRED`, `DEFERRED`, `REVIEW_DUE`, `REJECTED`, `CONFLICT`, and `INVALID`. Repository policy may shorten the 14-day request, seven-day approval, or 30-day defer windows but cannot extend them or disable required human and bound-evidence controls. A second receipt must explicitly supersede the current receipt for that request.

Promotion preflight returns `READY` only for an active, unsuperseded `APPROVE` receipt whose request, candidates, human evidence, and accepted decision memory still pass integrity checks. It returns a compatible approval payload but does not write that payload, invoke `baseline promote`, or mutate a baseline.

The `human:` authority identifier provides repository traceability only. It does not prove cryptographic identity; signed identity-provider or protected-environment verification remains future work.

## Slice 1 product proof - 2026-08-21

- QuietPilot remains `REVIEWABLE`; no approval receipt exists because human visual and semantic acceptance has not been supplied.
- QuotePilot receipt `BDR-B597544BA89A63A0` records the existing user hold as `DEFER`, audits `PASS`, and is review-due after `2026-09-04T17:00:00Z`.
- Lifecycle evaluation reports one `REVIEWABLE` request and one `DEFERRED` request.
- The hardened local full tier passed 42 tests, five-viewport fixture QA, quality 100/100, drift 0, three deterministic repair cycles, five V1 skill validators, dependency audit, and self-audit.
- The governed baseline manifest SHA-256 remains `03346893f7b9dff8fdd01de647908fb581af1a943ca258ac428057bca65aeef1`.

## Deferred V3 work

Later V3 slices may add:

- protected-environment or signed identity adapters for review receipts
- cross-browser evidence policy beyond Chromium
- federated read-only product evidence ingestion
- PR annotations that link requests without granting write authority
- human UAT outcome feedback into institutional memory

These are deferred until Slices 0 and 1 are proven remotely. Baseline thresholds, authority requirements, and repair limits are not candidates for weakening.
