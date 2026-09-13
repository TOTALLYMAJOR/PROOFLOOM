# Design Intelligence Feature Matrix

## Status meanings

| Status | Meaning |
|---|---|
| `IMPLEMENTED` | A repository implementation and automated proof exist. The status does not imply deployment or adoption in a consuming repository. |
| `FOUNDATION` | The deterministic local contract exists; external adapters, product pilots, or operational proof remain required. |
| `PROPOSED` | Documented direction only; it must not be represented as available behavior. |

## Capability matrix

| ID | Capability | Status | Primary interface | Evidence or boundary |
|---|---|---|---|---|
| DI-GOV-001 | Repository governance convergence | `IMPLEMENTED` | `design-intelligence govern` | Maps and verifies existing authorities before material design work. |
| DI-MSN-001 | Plain-English design mission | `IMPLEMENTED` | `design-intelligence "<task>"` | Recommends directions; explicit selection remains mandatory. |
| DI-REF-001 | Evidence-bound reference adoption | `IMPLEMENTED` | `adopt`, `adoption-audit` | References begin `RESEARCH_REQUIRED`; adoption cannot self-authorize. |
| DI-MEM-001 | Scoped institutional design memory | `IMPLEMENTED` | `memory` | Hash-bound, append-oriented, and subordinate to repository authorities. |
| DI-QA-001 | Five-viewport rendered QA | `IMPLEMENTED` | `npm run design:qa` | Local rendered proof only; no hosted or customer-outcome claim. |
| DI-BAS-001 | Human-governed baseline lifecycle | `IMPLEMENTED` | `baseline` | Requests and receipts do not silently mutate baselines. |
| DI-RPR-001 | Exact bounded visual repair | `IMPLEMENTED` | `repair` | Allowlisted text substitution, evidence-linked, maximum three iterations. |
| DI-CTL-001 | Repository-native development control plane | `IMPLEMENTED` | `devctl` | Indexes existing authorities and checks; does not create a second backlog. |
| DI-ARC-001 | Bounded architecture impact graph | `IMPLEMENTED` | `devctl architecture impact` | Static downstream impact is not proof of runtime execution. |
| DI-AF-001 | Hash-bound AgentFlow handoff and receipt audit | `IMPLEMENTED` | `agentflow` | AgentFlow owns execution; receipt proof remains limited to its declared boundary. |
| DI-AGT-001 | Just-in-time authority capsules | `IMPLEMENTED` | `agentic capsule` | Source-verified, phase-bounded context; always reports `implementationAuthorized: false`. |
| DI-AGT-002 | Executable UX state coverage | `IMPLEMENTED` | `agentic state-graph` | Detects reachability, negative-state, dead-end, and recovery gaps without adding a test hierarchy. |
| DI-AGT-003 | Counterfactual design comparison | `IMPLEMENTED` | `agentic simulate` | Falsifiable evidence scoring; protected boundaries and human selection fail closed. |
| DI-AGT-004 | Governed design arena evaluation | `FOUNDATION` | `agentic arena` | Deterministic comparison is implemented; AgentFlow execution and a consuming-repository pilot remain external. |
| DI-AGT-005 | Dual-loop outcome assessment | `FOUNDATION` | `agentic outcome` | Contract evaluation is implemented; runtime adapters and human-ratified product pilot remain open. |
| DI-V6-001 | Read-only runtime evidence adapters | `PROPOSED` | V6 roadmap | Must reuse existing analytics, error, support, accessibility, and release evidence. |
| DI-V6-002 | Governed outcome-to-memory promotion | `IMPLEMENTED` | `agentic outcome-ratify`, `outcome-promote`, `outcome-retire` | Hash-bound, expiring human receipts append to the existing outcome ledger; retirement adds a deprecated decision revision and preserves history. |
| DI-V6-003 | Cross-browser governed evidence | `IMPLEMENTED` | `npm run design:qa:cross-browser` | Chromium, Firefox, and WebKit run isolated evidence paths; legacy Chromium baselines never apply to another engine. |

## New agentic proof

`tests/test_agentic_capabilities.py` covers packaged schemas, source integrity and bounded ordering, state and recovery gaps, counterfactual boundary enforcement, arena equivalence/isolation/review gates and dissent, observation-window enforcement, human memory ratification, and explicit-output behavior. `tests/test_outcome_lifecycle.py` proves human-only ratification and retirement, assessment hash binding, receipt expiry, canonical outcome append, and replay rejection. `scripts/design/verify-cross-browser-policy.mjs` proves three-engine selection and browser-scoped baseline isolation; the standard CI tier executes all three engines across the governed five-viewport scenario.

The matrix records reusable utility capability. A consuming repository must still bind its own authorities, journeys, tests, thresholds, execution receipts, release evidence, and human approvals before making stronger claims.
