# Autonomous Design Department V3

## Status

V3 is in development on top of the merged V2 foundation. Slice 0 establishes the governance prerequisites for remote execution and future baseline review. It does not declare a V3 release and does not change the package version.

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

## Deferred V3 work

Later V3 slices may add:

- protected-environment or signed approval adapters for the existing promotion command
- cross-browser evidence policy beyond Chromium
- federated read-only product evidence ingestion
- retention and stale-request lifecycle rules
- PR annotations that link requests without granting write authority
- human UAT receipts and outcome feedback into institutional memory

These are deferred until Slice 0 is proven remotely. Baseline thresholds, authority requirements, and repair limits are not candidates for weakening.
