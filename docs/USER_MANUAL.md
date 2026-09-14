# Design Intelligence User Manual

<p align="center">
  <img src="../artifacts/design/brand/design-intelligence-brand-concept-v2.png" alt="Proofloom — Design that can show its work" width="760">
</p>

Proofloom is the visual mark for Design Intelligence. The repository, Python package, and command-line interface retain the `design-intelligence` name.

This manual is the task-oriented guide for operators, designers, developers, and coding agents. It explains how to move from repository evidence to a governed design direction, implementation constraints, rendered proof, and durable learning without replacing the consuming repository's own authorities.

## Operating contract

Design Intelligence follows this authority order:

1. explicit current user instruction;
2. existing product behavior and requirements;
3. repository governance, architecture, and design authorities;
4. existing tokens, components, and implementation patterns;
5. reviewed references and general conventions.

The tool is read-only by default. A recommendation is not approval, an output artifact is not implementation authorization, and local or CI evidence is not hosted, production, customer-acceptance, or business-outcome proof.

## Install and verify

Requirements:

- Python 3.11 or newer;
- Node.js and npm only when using reference capture or rendered QA;
- Playwright browser binaries only when running browser evidence.

From the Design Intelligence checkout:

```bash
./scripts/install
design-intelligence --help
devctl --help
```

The installer links `design-intelligence` and `devctl` into `~/.local/bin` and installs the Codex skills. If that directory is not on `PATH`, follow the command printed by the installer and restart the shell.

For rendered QA:

```bash
npm install
npx playwright install chromium firefox webkit
```

## Choose the right workflow

| Goal | Start here | Result |
|---|---|---|
| Choose from standard operations in a local interface | `design-intelligence shell --root <repo> --open` | Proofloom Launchpad bound to the repository and its current evidence |
| Explore a design task | `design-intelligence "<task>"` | Read-only repository inspection and three direction briefs |
| Save an approved direction | `design-intelligence "<task>" --direction recommended --save` | Mission bundle under `artifacts/design/missions/` |
| Stabilize a mature repository | `design-intelligence govern audit --root <repo>` | Authority and readiness diagnosis before design |
| Use an external reference | `design-intelligence adopt ...` | Evidence-bound adoption report and optional design contract |
| Retrieve design memory | `design-intelligence memory context ...` | Bounded inherited rules, decisions, outcomes, debt, and exceptions |
| Prepare agent context | `design-intelligence agentic capsule ...` | Source-verified, phase-bounded authority capsule |
| Transfer approved work to AgentFlow | `design-intelligence agentflow handoff-create ...` | Versioned, hash-bound handoff |
| Run rendered QA | `npm run design:qa` | Local five-viewport evidence |
| Check the whole repository program | `devctl program status --root <repo>` | Joined governance, journey, architecture, design, backlog, and evidence status |

Replace `<repo>` with an absolute or repository-relative path. Commands that accept `--root` default to the current directory unless their help states otherwise.

## Use the Proofloom Operator Shell

Start the governed local interface from the repository you want to work on:

```bash
design-intelligence shell --root /path/to/repository --port 8787 --open
```

The Launchpad is prepopulated with Reformat surface, Governance audit, Design audit, UX audit, Backlog health, Build proposed backlog, and Visual QA. Choosing an operation updates the task fields, action class, named authority, proof boundary, and single safe next action. The evidence rail keeps the bound repository, source revision, write posture, and execution authority visible while you work. Full structured evidence remains available behind progressive disclosure.

Action classes have distinct meanings:

- `inspect` reads and reports repository evidence;
- `propose` prepares a direction or governed handoff for review;
- `execute` names an explicit local evidence action but does not run it implicitly.

The shell listens only on `127.0.0.1` or `localhost`, uses a same-session token for operations, and exposes no free-form command field. It does not create a canonical backlog or execute AgentFlow. The Build proposed backlog option stages the evidence and review boundary; a reviewed, committed handoff is still required before AgentFlow planning or execution.

## 1. Start a design mission

Run the shortest path from the repository you want to improve:

```bash
cd /path/to/repository
design-intelligence "Improve the proposal comparison flow"
```

The command inspects the repository, infers the surface type, proposes three product-fit directions, recommends one, identifies reference-research needs, and defines the rendered-proof gate. It does not write files or authorize implementation.

After a human reviews and selects a direction:

```bash
design-intelligence "Improve the proposal comparison flow" \
  --direction recommended \
  --save
```

The saved bundle contains the mission, reference ledger, agent handoff, and approved design contract. A named direction ID can be used instead of `recommended`.

Use the detailed workflow when you need to inspect intermediate planning:

```bash
design-intelligence work \
  --root /path/to/repository \
  --task "Improve the proposal comparison flow" \
  --profile quotepilot

design-intelligence handoff \
  --root /path/to/repository \
  --task "Improve the proposal comparison flow" \
  --profile quotepilot \
  --output work/handoff.md
```

`work` writes only when an explicit output option is supplied. `handoff` writes only the named output file and does not transfer execution authority.

## 2. Govern a mature repository before design

Use the governance lifecycle when a repository has competing instructions, unclear journeys, authority drift, a fragmented backlog, or an existing control plane:

```bash
design-intelligence govern audit --root /path/to/repository
design-intelligence govern plan --root /path/to/repository
design-intelligence govern apply --root /path/to/repository
design-intelligence govern verify --root /path/to/repository
```

- `audit` maps tracked product, journey, architecture, backlog, design, security, delivery, instruction, skill, hook, and proof authorities.
- `plan` orders convergence work without executing repository commands.
- `apply` writes only derived bindings and drift protection under `.dev/governance/`.
- `verify` checks the generated convergence baseline against current authorities.

If a critical authority changed after a convergence manifest was established, ordinary apply fails closed. A repository owner must review the change and provide an exact `AuthorityDriftRatification` receipt:

```bash
design-intelligence govern apply \
  --root /path/to/repository \
  --ratification /path/to/owner-receipt.json
```

Do not create or broaden a ratification receipt on an owner's behalf. `DESIGN_READY` means the repository is coherent enough to begin design; it does not mean the product is complete, merged, released, deployed, or accepted by customers.

## 3. Use references without copying them blindly

Every supplied URL or image begins as `RESEARCH_REQUIRED`. Capture the source, record typed observations and transformations, then run the deterministic adoption gate:

```bash
npm run design:reference:capture -- \
  --url https://example.com/design \
  --output artifacts/design/references/example

design-intelligence adopt "Improve proposal comparison" \
  --root /path/to/repository \
  --reference https://example.com/design \
  --analysis artifacts/design/references/example/reference-analysis.json \
  --governance-receipt /path/to/review-receipt.json \
  --save \
  --strict

design-intelligence adoption-audit \
  --root /path/to/repository \
  --input artifacts/design/adoptions/improve-proposal-comparison/adoption-report.json
```

For a local image, replace `--reference` with repeatable `--image` options. The gate returns one of:

- `READY`: every pattern is eligible for `ADOPT` or `ADAPT`;
- `REVIEW_REQUIRED`: a human must resolve capabilities, stale memory, debt, or design-system conflicts;
- `RESEARCH_REQUIRED`: typed, evidence-bound analysis is missing;
- `DECLINED`: the patterns are unsupported or inappropriate;
- `BLOCKED`: an integrity, authority, architecture, or protected-rule boundary was crossed.

Adoption reports do not implement code, change baselines, or approve a design direction.

## 4. Initialize and query design memory

For an established repository, integrate with its existing truth instead of installing competing defaults:

```bash
design-intelligence memory init \
  --root /path/to/repository \
  --integrate-existing \
  --memory-only
```

Bind `.design/memory/product-rules.json` to canonical repository sources. In `index-only` mode, every summarized rule must name a source authority and its SHA-256; missing or changed sources fail closed.

Retrieve only the context needed for a task:

```bash
design-intelligence memory context \
  --root /path/to/repository \
  --product quotepilot \
  --surface QuoteWorkspace \
  --component QuoteSidebar
```

Before material UI or design-system implementation, run the memory gate:

```bash
design-intelligence memory audit --root /path/to/repository --format json

design-intelligence memory preflight \
  --root /path/to/repository \
  --product quotepilot \
  --surface QuoteWorkspace \
  --max-records 40 \
  --format json
```

Preflight returns:

- `ALLOW` for structurally valid memory with no scoped review conditions;
- `WARN` when implementation may continue only after reviewing advisory decisions, exceptions, rejected outcomes, stale records, debt, or bounded retrieval;
- `BLOCK` for missing, malformed, contradictory, drifted, or protected-rule-conflicting memory.

Memory is append-oriented. Do not rewrite earlier decisions or outcomes to make the current state look cleaner.

## 5. Create and validate implementation evidence

Useful repository checks include:

```bash
design-intelligence inspect --root /path/to/repository
design-intelligence assess --root /path/to/repository
design-intelligence context --root /path/to/repository --profile quotepilot
design-intelligence lint --root /path/to/repository
design-intelligence refactor-risk --root /path/to/repository
design-intelligence doctor --root /path/to/repository
design-intelligence self-audit --root /path/to/repository
```

Validate a design contract and aggregate existing review evidence:

```bash
design-intelligence contract validate --input work/design-contract.json
design-intelligence review --input work/review-manifest.json
design-intelligence validate \
  --root /path/to/repository \
  --review-input work/review-manifest.json \
  --evidence-pack-out work/evidence-pack.md
```

Use the consuming repository's existing E2E hierarchy. Design Intelligence adds design evidence and proposed scenarios; it must not establish a second product test hierarchy.

## 6. Run rendered and cross-browser QA

In this repository, run:

```bash
npm run design:qa
npm run design:qa:cross-browser
npm run design:qa:cross-browser:policy
npm run design:repair:prove
```

The governed scenario exercises 1440, 1280, 1024, 768, and 390 pixel widths. Reports include screenshots, DOM and state checks, overflow and off-screen control checks, accessibility evidence, contract evidence, and visual comparisons where an approved baseline applies.

Browser evidence is isolated by engine. Existing top-level viewport baselines apply only to Chromium. Firefox and WebKit use browser-specific baseline entries; without them, they produce structural evidence and mark visual comparison `NOT_RUN`.

To preview this repository's static QA fixture manually:

```bash
python3 -m http.server 8123 \
  --bind 127.0.0.1 \
  --directory tests/fixtures/visual-surface
```

Open `http://127.0.0.1:8123/`. This repository does not expose an `npm run dev` application server. The fixture preview is a bounded local review surface, not hosted or production proof.

### Baseline governance

Baseline candidates require an explicit review lifecycle:

```bash
design-intelligence baseline request \
  --root /path/to/repository \
  --scenario surface \
  --product Product \
  --qa-report qa-report.json \
  --model-review model-review.json \
  --candidate-root screenshots/surface \
  --requested-by agent:codex \
  --output baseline-request.json

design-intelligence baseline request-audit \
  --root /path/to/repository \
  --input baseline-request.json

design-intelligence baseline decide \
  --root /path/to/repository \
  --request baseline-request.json \
  --decision human-decision.json \
  --output review-receipt.json

design-intelligence baseline receipt-audit \
  --root /path/to/repository \
  --input review-receipt.json

design-intelligence baseline preflight \
  --root /path/to/repository \
  --receipt review-receipt.json
```

Requests, decisions, receipts, and preflight do not silently replace a baseline. Never update a baseline merely to make a failing comparison pass.

### Bounded repair

Repair is explicit, allowlisted, evidence-linked, and limited to three iterations:

```bash
design-intelligence repair \
  --root /path/to/repository \
  --plan repair-plan.json \
  --evidence qa-report.json \
  --iteration 1 \
  --apply
```

Repair stops at authority, scope, architecture, baseline, threshold, test, backend, or product-behavior boundaries.

## 7. Hand approved work to AgentFlow

Design Intelligence and AgentFlow exchange versioned, hash-bound documents; they do not share a database or transfer authority implicitly.

```bash
design-intelligence agentflow handoff-create \
  --input work/governed-handoff-input.json \
  --output work/governed-task-handoff.json

design-intelligence agentflow handoff-validate \
  --input work/governed-task-handoff.json

design-intelligence agentflow receipt-audit \
  --input work/agentflow-build-receipt.json \
  --handoff work/governed-task-handoff.json
```

The operating sequence is:

1. Design Intelligence creates a `design-intelligence/governed-task-handoff`.
2. A repository owner reviews and approves the exact handoff.
3. AgentFlow verifies the handoff and source commit before planning.
4. AgentFlow binds the handoff digest to its immutable plan and execution evidence.
5. AgentFlow emits an `agentflow/build-receipt`.
6. Design Intelligence audits that receipt against the exact handoff.

A `PROPOSED` handoff cannot authorize execution. A passing receipt proves only its declared execution and integration boundary.

## 8. Use the agentic development tools

The analysis flow is:

```text
authority capsule
  -> UX state coverage
  -> counterfactual comparison
  -> governed arena evaluation
  -> outcome assessment
  -> human-ratified memory promotion
```

Create source-verified, phase-bounded context:

```bash
design-intelligence agentic capsule \
  --root /path/to/repository \
  --input work/authority-capsule-input.json \
  --phase implement \
  --max-claims 20 \
  --output work/authority-capsule.json
```

Find missing journey states and recovery paths:

```bash
design-intelligence agentic state-graph \
  --input work/journey-state-input.json \
  --output work/journey-state-report.json
```

Compare falsifiable alternatives and protected boundaries:

```bash
design-intelligence agentic simulate \
  --input work/counterfactual-input.json \
  --output work/counterfactual-report.json
```

Compare at least two contract-equivalent, independently reviewed variants:

```bash
design-intelligence agentic arena \
  --input work/design-arena-input.json \
  --output work/design-arena-report.json
```

Assess declared product and agent-effectiveness signals after the observation window closes:

```bash
design-intelligence agentic outcome \
  --input work/outcome-contract-and-evidence.json \
  --as-of 2026-09-30T00:00:00Z \
  --output work/outcome-assessment.json
```

`capsule`, `state-graph`, and `simulate` are implemented analysis capabilities. `arena` and `outcome` provide implemented deterministic foundations, but still require external execution/runtime adapters and consuming-repository proof. None of these commands authorizes implementation, selects a direction, executes AgentFlow, deploys, or proves causality.

### Promote or retire an outcome

Promotion requires a separate human decision bound to the exact assessment:

```bash
design-intelligence agentic outcome-ratify \
  --root /path/to/repository \
  --assessment work/outcome-assessment.json \
  --decision work/human-outcome-decision.json \
  --output work/outcome-ratification.json

design-intelligence agentic outcome-ratification-audit \
  --root /path/to/repository \
  --input work/outcome-ratification.json

design-intelligence agentic outcome-promote \
  --root /path/to/repository \
  --receipt work/outcome-ratification.json
```

`authorizedBy` must use a `human:` identity. A `PROMOTE` receipt is bound to the assessment, expires after seven days, requires a `DO-` outcome ID, and can append exactly once to `.design/memory/outcomes.jsonl`.

When later evidence invalidates an accepted decision:

```bash
design-intelligence agentic outcome-retire \
  --root /path/to/repository \
  --input work/human-retirement-decision.json
```

Retirement appends a `deprecated` decision revision. It does not delete history.

## 9. Use the development control plane

`devctl` indexes and coordinates existing repository authorities; it does not become a second product, architecture, design, backlog, or test authority.

Start with a dry run:

```bash
devctl init --dry-run --root /path/to/repository
```

After reviewing detected authorities and gaps, initialize the additive manifest and task store:

```bash
devctl init --root /path/to/repository
devctl validate --root /path/to/repository
devctl doctor --root /path/to/repository
devctl planes audit --root /path/to/repository
devctl backlog status --root /path/to/repository
devctl health --root /path/to/repository
```

For bounded work and affected verification:

```bash
devctl intelligence route TASK-ID --root /path/to/repository
devctl task context TASK-ID --root /path/to/repository
devctl verify affected TASK-ID \
  --root /path/to/repository \
  --changed src/App.tsx
```

For a mature repository's full finalization view:

```bash
devctl program status --root /path/to/repository
devctl program plan --root /path/to/repository
devctl program complete --root /path/to/repository
```

`program plan` does not execute repository commands. `program complete` fails unless every control gate passes and every completion-governed backlog item has an evidence-backed terminal disposition.

## 10. Run the appropriate CI tier

```bash
npm run design:ci:quick
npm run design:ci:standard
npm run design:ci:full
```

| Tier | Use it for | Coverage |
|---|---|---|
| `quick` | Core, governance, contract, memory, registry, or documentation changes | Unit and governance tests, convergence, contracts, memory, baselines, registry, and diff hygiene |
| `standard` | Material rendered changes | Quick checks plus five-viewport Chromium scoring, isolated three-browser evidence, and an integrated evidence pack |
| `full` | Release candidates | Standard checks plus three repair cycles, dependency audit, skill validation, and self-audit |

Run `devctl validate` and `devctl doctor` after changing control-plane declarations. Run `govern audit`, `plan`, and `verify` after changing critical product understanding or governance. Run `planes audit`, `backlog status`, and `health` after changing intent, journeys, standards applicability, intelligence routing, or backlog sources.

## Write and authority boundaries

| Action | Writes? | Authority boundary |
|---|---:|---|
| Inspect, assess, lint, context, doctor, audit, plan, verify | No | Reports current evidence only |
| Plain-English mission without save/output options | No | Recommendation only |
| `--save`, `--save-to`, `--contract-out`, or `--output` | Yes | Writes only the declared generated artifact |
| `govern apply` | Yes | Derived `.dev/governance/` files only |
| Reference adoption | With `--save` | Adoption evidence; never implementation approval |
| Baseline request or decision | Yes | Request/receipt only; no silent baseline replacement |
| `repair --apply` | Yes | Exact allowlisted repair, maximum three iterations |
| Outcome ratification | Yes | Named receipt only |
| Outcome promotion | Yes | One append to the canonical outcome ledger |
| Outcome retirement | Yes | One preserved `deprecated` decision revision |

When reporting results, name the proof layer exactly: source inspection, local validation, CI, hosted/provider behavior, production state, customer acceptance, or measured outcome. Never infer a stronger layer from a weaker one.

## Troubleshooting

| Symptom | Meaning | Next action |
|---|---|---|
| `design-intelligence: command not found` | The CLI link is missing or `~/.local/bin` is not on `PATH` | Run `./scripts/install`, apply its printed PATH instruction, and restart the shell |
| Governance status is `UNDERSTANDING_INCOMPLETE` | One or more governing product authorities are absent or unresolved | Read the audit and complete the named vision, journey, architecture, backlog, or proof authority |
| `govern apply` reports authority drift | A critical bound source changed after convergence | Have the repository owner review the exact paths and digest; use a scoped ratification receipt only if approved |
| Memory preflight returns `BLOCK` | The ledger or a bound authority is invalid or contradictory | Repair the named source, hash, lifecycle, or protected-rule issue; do not bypass the gate |
| A reference remains `RESEARCH_REQUIRED` | Typed observations and transformations are missing | Capture/analyze the reference and rerun `adopt` plus `adoption-audit` |
| Firefox or WebKit visual comparison is `NOT_RUN` | No approved baseline exists for that browser | Treat structural evidence as the available proof or run the human baseline-review lifecycle |
| A visual comparison fails | The render differs from its approved baseline | Investigate the implementation or request a reviewed new baseline; never update it silently |
| The fixture URL does not load | The bounded static server is not running or the port is occupied | Start the documented Python server on an available loopback port and use that port in the URL |
| AgentFlow receipt audit fails | The receipt does not bind the exact handoff or declared evidence | Reconcile the source commit, handoff digest, plan, and execution evidence in AgentFlow |
| Outcome promotion fails | The receipt is invalid, expired, replayed, or not human-authorized | Generate a fresh assessment and obtain a new exact human decision; do not edit the old receipt |

## Further reference

- [Feature Matrix](FEATURE_MATRIX.md) — capability status and proof boundaries
- [Architecture](ARCHITECTURE.md) — package structure and authority model
- [Repository Rehabilitation and Finalization](REPOSITORY-REHABILITATION-AND-FINALIZATION.md) — mature-repository governance
- [Design Memory Preflight](DESIGN-MEMORY-PREFLIGHT.md) — memory lifecycle and implementation gate
- [Agentic Development Extensions](AGENTIC-DEVELOPMENT.md) — agentic input contracts and evidence rules
- [AgentFlow Integration](AGENTFLOW-INTEGRATION.md) — governed handoff and receipt contract
- [Claim Boundary Registry](CLAIM-BOUNDARY-REGISTRY.md) — safe claim language and required evidence
