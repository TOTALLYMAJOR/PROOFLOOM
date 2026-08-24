# V6 Runtime-Outcome Learning: Proposed Scope

## Purpose

V5 determines whether a repository is governed and ready to enter design work. V6 should close the learning loop after a governed change reaches real users:

```text
approved change -> release evidence -> bounded runtime signals -> outcome assessment -> memory candidate -> human ratification
```

It must not turn operational telemetry into unchecked design authority.

## Phase A: Outcome Contracts

Require a human-owned outcome contract before a governed change can be observed. The contract names the user journey, expected user behavior, success and counter-signals, observation window, privacy classification, data owner, and rollback signal. It binds to the change, release evidence, and existing product requirement without duplicating the product backlog.

## Phase B: Read-Only Evidence Adapters

Introduce repository-local adapters that read existing analytics, error, support, accessibility, and release evidence. Adapters produce bounded, normalized evidence packs with source timestamps, retention limits, tenant/privacy constraints, and explicit unknowns. They must never collect secrets, export raw personal data, or create a second analytics system.

## Phase C: Outcome Evaluation

Evaluate each contract deterministically where possible: release present, observation window complete, required signals available, success thresholds met, and counter-signals absent or explained. Model assistance may summarize evidence and propose explanations, but cannot decide success, alter thresholds, or approve a design decision.

## Phase D: Institutional Learning

Create a reviewable memory candidate only when an outcome is evidence-backed. The candidate links the original decision, implementation, rendered verification, release, measured outcome, and exceptions. A human must ratify any product-, portfolio-, archetype-, security-, accessibility-, or architecture-level rule before it is inherited.

## Phase E: Drift and Retirement

Continuously mark stale contracts, expired observations, broken adapters, superseded decisions, and unresolved counter-signals. Staleness blocks promotion of a learning claim; it does not rewrite history. Retire rules only through the existing human-authority and supersession paths.

## Non-Goals

- no autonomous deployment, rollback, baseline promotion, pricing change, or product-scope change
- no cross-repository telemetry warehouse or copied authority graph
- no inference that a design succeeded merely from a deploy, page view, or missing error report
- no weakening of V5 governance, repair limits, visual thresholds, or privacy constraints

## Entry and Exit Criteria

Start only after a product selects one bounded journey and identifies an existing runtime-evidence source. The first pilot should be read-only and compare one shipped change against one predeclared outcome contract. Exit the pilot only after provenance, privacy, data freshness, false-positive handling, and human-ratification workflow are proven end to end.

## Decisions Still Required

- which repository supplies the first pilot journey and its named owner
- which existing runtime evidence source may be read, under what retention and tenant boundaries
- what outcome threshold and counter-signal are valid for that journey
- which human role ratifies a learning candidate and who can retire it
