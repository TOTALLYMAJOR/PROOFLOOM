# Development Control Plane Phase 0 Gap Map

Phase 0 reconciles the proposed AI-native development control plane with the repository before adding infrastructure. The governing decision is additive integration: Design Intelligence remains the design capability, while `devctl` indexes repository authorities and selects existing commands.

| Control-plane concern | Existing authority | Decision | Phase 0-3 result |
|---|---|---|---|
| Agent instructions | `AGENTS.md`, `adapters/*` | Keep | Indexed by `devctl.yaml`; not copied into `.dev`. |
| Architecture | `docs/ARCHITECTURE.md` | Keep | Declared as a trust-ranked domain authority. |
| Design language | `docs/design/DESIGN-LANGUAGE.md` | Keep | Retrieved through bounded context. |
| Design decisions/outcomes/exceptions/debt | `.design/memory/` | Keep | Delegated; no `.dev` memory ledger is created. |
| Scoped design-rule inheritance | `.design/memory/product-rules.json` | Keep | Existing portfolio-to-exception rules remain canonical. |
| Design contracts | Existing schema and contract CLI | Keep | Selected as task context or verification evidence. |
| Component registry | `.design/memory/component-registry.json` | Keep | Existing scanner/auditor remains canonical. |
| Visual scenarios | `tests/design/scenarios/` | Keep | `devctl visual` points to the existing Playwright hierarchy. |
| Visual baselines | `.design/baselines/` | Keep | Existing human-governed manifests and receipts remain canonical. |
| Quality thresholds | `.design/quality/thresholds.json` | Keep | Audited without lowering or rewriting thresholds. |
| Bounded repair | Existing repair engine | Keep | Not reimplemented and not automatically invoked by Phase 0-3. |
| Repository manifest | None | Add | One `devctl.yaml`, expressed as dependency-free JSON-compatible YAML. |
| Task packets | No canonical repository task packet | Add | `.dev/tasks/{active,blocked,completed}` stores only bounded execution packets. |
| Context selection | Design-only bounded retrieval | Adapt | Adds trust-ranked repository/task/source selection with file and byte ceilings. |
| Change impact | CI tiers existed without path selection | Add | Deterministic path-to-check rules produce a read-only affected-verification plan. |
| Central service, graph DB, policy engine | None required | Defer | No server, graph database, OPA layer, or parallel orchestration service. |
| Autonomous command execution | Existing explicit operator/CI commands | Defer | Phase 0-3 plans commands but never executes arbitrary task-supplied commands. |

## Authority boundary

`.dev` does not own design truth, product truth, release authority, or source code. It owns only the manifest version and explicit task packets. A consuming repository's existing governance, backlog, architecture, hooks, tests, components, tokens, and deployment controls continue to outrank package defaults.

## Duplication test

Initialization must not create `.design`, baselines, thresholds, a component registry, a backlog, or an E2E directory. If `devctl.yaml` already exists, initialization is idempotent and writes nothing. Missing declared authorities fail validation instead of being silently replaced.
