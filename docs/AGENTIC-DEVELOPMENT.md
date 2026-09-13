# Agentic Development Extensions

## Purpose

The `design-intelligence agentic` command family helps coding agents make better design decisions from bounded evidence. It extends the repository's existing mission, control-plane, visual-QA, memory, and AgentFlow contracts; it does not become a second backlog, test hierarchy, execution coordinator, analytics store, or approval authority.

The five analysis commands are read-only unless `--output` is supplied. An output is an evidence artifact, never implementation authorization. The outcome lifecycle subcommands are separately explicit: ratification writes only its named receipt, promotion appends one canonical outcome, and retirement appends one deprecated decision revision.

## Capability flow

```text
bounded authority capsule
  -> executable UX state coverage
  -> counterfactual direction comparison
  -> contract-equivalent design arena
  -> release-bound outcome assessment
  -> human-ratified learning candidate
```

## 1. Just-in-time authority capsules

`capsule` selects only claims relevant to the current agent phase, orders them by repository authority and declared priority, verifies repository-relative SHA-256 sources, and exposes stale, contested, unknown, and conflicting claims.

```bash
design-intelligence agentic capsule \
  --root /path/to/repo \
  --input work/authority-capsule-input.json \
  --phase implement \
  --max-claims 20 \
  --output work/authority-capsule.json
```

An `ESTABLISHED` claim without a valid source fails closed. `READY` means the selected capsule is internally valid; `implementationAuthorized` remains `false` because the consuming repository owns authorization.

## 2. Executable UX state graph

`state-graph` checks a declared journey for a start, reachable success, required state kinds, unreachable states, accidental dead ends, and explicit recovery from failure states. It produces proposed scenarios and measurable acceptance criteria for gaps.

```bash
design-intelligence agentic state-graph \
  --input work/journey-state-input.json \
  --output work/journey-state-report.json
```

The command does not create tests. Proposed scenarios must be reconciled into the repository's existing E2E hierarchy.

## 3. Counterfactual design simulation

`simulate` compares alternatives using declared effects, evidence, confidence, falsification tests, rollback signals, and protected-boundary impacts.

```bash
design-intelligence agentic simulate \
  --input work/counterfactual-input.json \
  --output work/counterfactual-report.json
```

An alternative is ineligible when it crosses an unapproved protected boundary, omits a falsification test, or has no rollback signal. A unique evidence-backed leader may be recommended, but human selection is always required and no production outcome is predicted.

## 4. Governed design arena

`arena` compares evidence from at least two variants without executing them. Every eligible variant must bind the same design-contract and validation-plan hashes, use an isolated workspace, carry a passing build receipt, complete the same required evidence dimensions and tests, include the required number of independent critiques, and have no critical or serious accessibility violations. Conflicting critic verdicts are retained as explicit dissent; a `BLOCKED` verdict makes the variant ineligible.

```bash
design-intelligence agentic arena \
  --input work/design-arena-input.json \
  --output work/design-arena-report.json
```

Variant names do not influence scoring; stable opaque labels are derived from the contract hash. AgentFlow remains the execution authority. A leader is evidence for human selection, not authority to integrate.

## 5. Dual-loop outcome learning

`outcome` evaluates a predeclared journey outcome only after its observation window closes and release plus signal evidence is present. Success signals define required achievement thresholds; counter-signals define acceptable safety bounds, so a failed counter-signal predicate produces `COUNTER_SIGNAL`. Optional agent-effectiveness signals are evaluated separately so product success cannot conceal inefficient or unsafe agent behavior.

```bash
design-intelligence agentic outcome \
  --input work/outcome-contract-and-evidence.json \
  --as-of 2026-09-30T00:00:00Z \
  --output work/outcome-assessment.json
```

A successful outcome with a bound `contract.decisionId` creates an eligible memory-candidate payload with `HUMAN_REQUIRED` ratification. The assessment command never appends memory, promotes a baseline, deploys, rolls back, or treats missing telemetry as success.

The durable lifecycle uses an exact assessment and a separate human decision:

```bash
design-intelligence agentic outcome-ratify \
  --root /path/to/repo \
  --assessment work/outcome-assessment.json \
  --decision work/human-outcome-decision.json \
  --output work/outcome-ratification.json
design-intelligence agentic outcome-ratification-audit \
  --root /path/to/repo \
  --input work/outcome-ratification.json
design-intelligence agentic outcome-promote \
  --root /path/to/repo \
  --receipt work/outcome-ratification.json
```

`authorizedBy` must identify a human authority with the `human:` prefix. A `PROMOTE` receipt is SHA-256-bound to the assessment, expires after seven days, requires a `DO-` outcome ID, and appends exactly once to `.design/memory/outcomes.jsonl`. It does not automatically accept the related design decision; the existing memory decision lifecycle remains authoritative.

When later evidence invalidates an accepted decision, retirement appends a `deprecated` revision instead of deleting either the decision or its outcomes:

```bash
design-intelligence agentic outcome-retire \
  --root /path/to/repo \
  --input work/human-retirement-decision.json
```

## Input contract summary

| Command | Required input |
|---|---|
| `capsule` | `taskId`, `phase`, and `claims`; established claims bind a repository-relative path and SHA-256 |
| `state-graph` | `journeyId`, `states`, `transitions`, and optional `requiredStateKinds` |
| `simulate` | `proposalId`, `alternatives`, and optional `protectedBoundaries` |
| `arena` | `arenaId`, `contractHash`, `validationPlanHash`, required evidence dimensions, independent reviews, and at least two variants |
| `outcome` | outcome `contract` including `decisionId`, `releaseEvidence`, and optional `agentSignals` |
| `outcome-ratify` | exact assessment plus a human `PROMOTE` or `REJECT` decision |
| `outcome-promote` | unexpired, hash-valid `PROMOTE` receipt |
| `outcome-retire` | accepted `decisionId`, human authority, and retirement reason |

The corresponding output schemas are distributed in `design_intelligence/data/schemas/`.

## Proof and authority boundaries

- `READY` or `PASS` proves only the deterministic checks named by that report.
- A capsule does not authorize work.
- A state graph does not prove runtime reachability.
- A counterfactual score does not prove causality or select a direction.
- An arena report does not prove that AgentFlow executed or integrated a variant unless supplied receipts establish that bounded fact.
- An outcome assessment does not prove deployment, production access, customer acceptance, or business impact beyond its declared evidence.
- Institutional learning remains append-oriented and human-ratified.
- A promotion receipt authorizes one canonical outcome append; it does not silently promote the related decision.
- Retirement preserves every earlier decision revision and outcome.

## Validation

```bash
python3 -m unittest tests.test_agentic_capabilities tests.test_outcome_lifecycle
npm run design:qa:cross-browser:policy
npm run design:ci:quick
```
