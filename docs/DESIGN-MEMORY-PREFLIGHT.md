# Design Memory Preflight

`design-intelligence memory preflight` is the deterministic gate between repository design memory and implementation. It does not approve a design or replace repository authority. It classifies the latest scoped decision revisions, validates the complete append-only ledger, and returns one of three statuses:

- `ALLOW`: memory is structurally and lifecycle-valid with no scoped review conditions.
- `WARN`: implementation may continue, but advisory decisions, active exceptions, rejected outcomes, stale records, unresolved debt, or bounded retrieval require explicit review.
- `BLOCK`: memory is missing, malformed, internally contradictory, source-authority hashes drifted, or protected rules conflict.

## Decision Classes

- `binding`: accepted decisions. These govern the matching scope.
- `advisory`: proposed or experimental decisions. These may challenge a binding decision but cannot supersede it.
- `historical`: superseded, deprecated, or rejected decisions. These remain evidence and cannot authorize implementation.

The backward-compatible `decisions` context field remains available, and every returned decision includes `memoryClass`. New consumers should use `binding_decisions`, `advisory_decisions`, and `historical_decisions`.

## Lifecycle Rules

1. Proposed and experimental decisions use `proposesSupersession`; they cannot use `supersedes`.
2. An accepted successor may use `supersedes` only when the target's latest revision is `superseded` and points back with `supersededBy`.
3. A later rejected outcome blocks an accepted decision until an append-only revision marks it deprecated, rejected, or superseded.
4. Accepted promotion outcomes must belong to the promoted decision and have result `accepted`.
5. Decision revisions must be unique and contiguous from revision 1; supersession cycles block preflight.
6. Historical invalid lifecycle declarations are preserved. A valid latest revision can rehabilitate lifecycle state without rewriting the ledger.

## Commands

```bash
design-intelligence memory audit --root /path/to/repository --format json

design-intelligence memory preflight \
  --root /path/to/repository \
  --product quietpilot \
  --surface CommandCenter \
  --max-records 40 \
  --format json
```

`BLOCK` exits non-zero. `ALLOW` and `WARN` exit zero so CI can fail on integrity or authority violations while teams retain an explicit review path for bounded warnings.

## Consumer Integration

1. Run preflight before meaningful UI or design-system implementation.
2. Read inherited rules and `bindingDecisions` as constraints.
3. Surface `advisoryDecisions`, warnings, and historical outcomes in the task packet; never silently promote them.
4. Run `memory audit` in CI against the whole ledger.
5. Keep `.design/memory/product-rules.json` in `index-only` mode when canonical repository documents remain authoritative.
6. Pin the engine revision used by CI so local and remote lifecycle behavior cannot drift silently.
