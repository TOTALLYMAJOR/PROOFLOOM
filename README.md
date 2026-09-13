# Design Intelligence with Repository Rehabilitation and Design Governance

Design Intelligence is a production-grade, vendor-neutral utility for repository-aware design work. Its core mission is design intelligence: understand product intent, preserve existing design truth, reason about UX and design-system change, validate rendered outcomes, and record evidence without turning into a second application scaffold.

The governing objective is:

> Product intent -> repository evidence -> design reasoning -> implementation constraints -> rendered validation -> design learning.

## Rehabilitate mature repositories before design

For a repository that has accumulated product drift, conflicting instructions, incomplete journeys, or years of partial backlog work, start here:

```bash
design-intelligence govern audit --root /path/to/repo
design-intelligence govern plan --root /path/to/repo
design-intelligence govern apply --root /path/to/repo
design-intelligence govern verify --root /path/to/repo
```

The audit maps tracked instructions, skills, hooks, vision, actors, requirements, journeys, architecture, ADRs, contracts, security, backlog, design, tests, and delivery controls. It preserves an equally effective existing model, identifies conflicts and broken controls, generates a bounded rehabilitation plan, detects later authority drift, and locks design until the repository is coherent enough to finish the product. See `docs/REPOSITORY-REHABILITATION-AND-FINALIZATION.md`.

## Development control plane, Phases 0-5

The optional `devctl` facade coordinates repository instructions, hash-bound intent and user journeys, whole-backlog accounting, contextual standards currency, vendor-neutral intelligence routing, bounded task context, affected verification, and the existing Design Intelligence/Playwright evidence systems without creating duplicate authorities.

```bash
devctl validate --root /path/to/repo
devctl govern audit --root /path/to/repo
devctl govern plan --root /path/to/repo
devctl govern apply --root /path/to/repo
devctl govern verify --root /path/to/repo
devctl doctor --root /path/to/repo
devctl init --dry-run --root /path/to/repo
devctl planes audit --root /path/to/repo
devctl backlog status --root /path/to/repo
devctl health --root /path/to/repo
devctl intelligence route TASK-ID --root /path/to/repo
devctl task context TASK-ID --root /path/to/repo
devctl verify affected TASK-ID --root /path/to/repo --changed src/App.tsx
devctl visual audit --root /path/to/repo --input artifacts/design/reports/example/qa-report.json
```

Start with `devctl init --dry-run --root /path/to/repo`, review the detected authorities, scripts, backlog sources, and readiness gaps, then use `devctl init` for the additive manifest and task-store directories. Initialization does not invent product intent, approve standards applicability, create design memory, create a competing backlog, or add an E2E hierarchy. Repository owners must bind reviewed intent, journey, standards, and capability-routing files before all planes can pass. See `docs/CONTROL-PLANE-PHASE-4.md`.

## The easy path

From the repository you want to improve:

```bash
design-intelligence "Improve the proposal comparison flow"
```

That one command inspects the current repository, infers the surface mode, produces three product-fit directions, recommends one, marks supplied references for honest research, and defines the rendered-proof gate. It is read-only.

To explicitly accept the recommendation and save a complete mission bundle:

```bash
design-intelligence "Improve the proposal comparison flow" --direction recommended --save
```

The bundle is written to `artifacts/design/missions/<task>/` and contains the mission, reference ledger, agent handoff, and approved design contract. Existing repository authorities still outrank every generated artifact.

When external references are supplied, direction selection does not authorize implementation. Capture the source, provide typed human/model observations, run the deterministic adoption gate, then attach the audited report:

```bash
npm run design:reference:capture -- --url https://example.com/design --output artifacts/design/references/example
design-intelligence adopt "Improve proposal comparison" --reference https://example.com/design --analysis artifacts/design/references/example/reference-analysis.json --governance-receipt /path/to/review-receipt.json --save --strict
design-intelligence "Improve proposal comparison" --reference https://example.com/design --direction recommended --adoption-report artifacts/design/adoptions/improve-proposal-comparison/adoption-report.json --save
```

Local images can be passed directly with repeatable `--image` flags. The analyzer supplies observations and repository-bound capability evidence only. Deterministic rules produce `ADOPT`, `ADAPT`, `DEFER`, `DECLINE`, or `BLOCKED` and compile permitted patterns into the existing design-contract format.

Image-backed missions use the same evidence gate:

```bash
design-intelligence adopt "Improve proposal comparison" --image references/example.png --analysis reference-analysis.json --save --strict
design-intelligence "Improve proposal comparison" --image references/example.png --direction recommended --adoption-report artifacts/design/adoptions/improve-proposal-comparison/adoption-report.json
```

## Design Adoption Gate

The gate evaluates the design system already present instead of assuming it is healthy. It discovers repository governance, backlog and requirement documents, architecture/design decisions, custom instructions, and hooks; retrieves at most 20 scoped institutional-memory records; and reconciles every observed reference pattern against product capability and protected risks.

Status meanings:

- `RESEARCH_REQUIRED`: a URL/image has no typed, evidence-bound analysis.
- `REVIEW_REQUIRED`: capabilities, stale memory, debt, or design-system conflicts require a human decision.
- `READY`: every pattern is deterministically `ADOPT` or `ADAPT`; an existing-format design contract is available.
- `DECLINED`: the supplied patterns are inappropriate or unsupported.
- `BLOCKED`: integrity, repository authority, architecture, or protected-rule boundaries were crossed.

Adoption bundles are append-only and contain the report, source analysis/request, repository authority map, design-system health audit, and optional contract. `adoption-audit` rehashes evidence and authorities and replays the decision engine. Capture, adoption, and audit do not implement code, run repair, mutate quality thresholds, or change baselines.

## What V3 adds

- one-command, current-repository startup from a plain-English task
- automatic `marketing`, `app-workflow`, `customer-proposal`, `mobile`, or `general` mode inference
- three product-fit direction briefs with one recommendation
- a hard direction-selection checkpoint before implementation
- an honest reference ledger where URLs and `DESIGN.md` files begin as `RESEARCH_REQUIRED`
- surface-specific rendered-proof requirements using the repository's existing browser hierarchy
- predictable mission bundles through the explicit `--save` convenience write
- governed human baseline review receipts and non-mutating promotion preflight

V2 remains intact:

- institutional design memory with scoped `portfolio -> archetype -> product -> surface -> component -> exception` inheritance
- append-oriented decisions, accepted/rejected outcomes, exceptions, debt, stale-record audits, and component registry
- schema-backed design contracts and bounded memory retrieval
- route-specific Playwright rendering across 1440, 1280, 1024, 768, and 390 widths
- screenshot, pixel-diff, DOM/state, overflow, off-screen control, contract, and axe evidence
- approval-bound baselines that the QA and repair paths cannot mutate
- deterministic quality and drift scoring with protected threshold floors
- exact, evidence-linked, allowlisted repair with a hard three-iteration limit
- quick, standard, and full CI tiers plus a repository self-audit

V1 remains intact:

- `design-intelligence inspect`: bounded repository discovery and capability mapping
- `design-intelligence assess`: scaffold reconciliation and preserve/integrate/add/migrate guidance
- `design-intelligence context`: UX and product context reasoning with QuotePilot, QuietPilot, and LeaguePilot profiles
- `design-intelligence review`: structured visual QA aggregation from existing browser or screenshot evidence
- `design-intelligence lint`: deterministic design drift, component, layout, and accessibility checks
- `design-intelligence refactor-risk`: knowledge-vs-runtime migration scoring and blast-radius analysis
- `design-intelligence validate`: combined repo-fit, lint, optional review, and evidence-pack output
- `design-intelligence doctor`: conservative repair planning and blockers summary
- `skills/`: concise Codex/Claude skills with progressive-disclosure references
- `adapters/codex` and `adapters/claude`: thin adapter guidance, not a competing governance layer
- `templates/` and `examples/product-profiles/`: reusable design artifacts and archetype examples

Agentic development extensions add five read-only decision and learning capabilities:

- source-verified, phase-bounded authority capsules
- UX state graphs that detect missing negative, reachability, dead-end, and recovery coverage
- falsifiable counterfactual comparison with protected-boundary gates
- contract-equivalent design-arena evaluation for isolated AgentFlow variants
- release-bound product-outcome and agent-effectiveness assessment with human-ratified memory candidates

These extensions analyze supplied evidence only. They do not execute AgentFlow, select a design direction, modify tests, promote memory, deploy, or claim production outcomes. See `docs/AGENTIC-DEVELOPMENT.md` and the status-qualified `docs/FEATURE_MATRIX.md`.

V3 baseline governance adds hash-bound review requests, append-only human decision receipts, protected review windows, stale/superseded lifecycle evaluation, and non-mutating promotion preflight. Requests and receipts never mutate a baseline or authorize repair by themselves. See `docs/design/AUTONOMOUS-DESIGN-DEPARTMENT-V3.md`.

## Non-goals

- SaaS server
- mandatory cloud database
- Docker requirement
- vector DB or knowledge graph as canonical source
- second component library
- second token system
- second backlog
- second E2E hierarchy
- broad autonomous restructuring

## Authority order

Repository truth outranks package defaults.

1. Explicit current user instruction
2. Existing product behavior and requirements
3. Existing repository governance
4. Existing architecture or design documentation
5. Existing tokens and component primitives
6. Existing implementation patterns
7. User-supplied references
8. Approved external references
9. General convention
10. Agent aesthetic preference

## CLI

Install the skills and CLI from the repository checkout:

```bash
./scripts/install
```

This creates a lightweight CLI link at `~/.local/bin/design-intelligence`; it does not require a global Python package install. If `~/.local/bin` is not already on `PATH`, the installer prints the exact next step.

Core commands:

```bash
design-intelligence "Improve proposal comparison"
design-intelligence "Improve proposal comparison" --direction recommended --save
design-intelligence start /path/to/repo "Improve proposal comparison" --profile quotepilot --reference https://aura.build
design-intelligence inspect --root /path/to/repo
design-intelligence govern audit --root /path/to/repo
design-intelligence govern plan --root /path/to/repo
design-intelligence govern apply --root /path/to/repo
design-intelligence govern verify --root /path/to/repo
design-intelligence assess --root /path/to/repo
design-intelligence context --root /path/to/repo --profile quotepilot
design-intelligence lint --root /path/to/repo
design-intelligence refactor-risk --root /path/to/repo
design-intelligence review --input work/review-manifest.json
design-intelligence validate --root /path/to/repo --review-input work/review-manifest.json --evidence-pack-out work/evidence-pack.md
design-intelligence doctor --root /path/to/repo
design-intelligence adopt "Improve proposal comparison" --root /path/to/repo --image references/example.png --analysis reference-analysis.json --save --strict
design-intelligence adoption-audit --root /path/to/repo --input artifacts/design/adoptions/improve-proposal-comparison/adoption-report.json
design-intelligence work --root /path/to/repo --task "Improve proposal comparison" --profile quotepilot
design-intelligence handoff --root /path/to/repo --task "Improve proposal comparison" --profile quotepilot --reference https://aura.build --output work/handoff.md
design-intelligence memory context --root /path/to/repo --product quotepilot --surface QuoteWorkspace --component QuoteSidebar
design-intelligence memory init --root /path/to/repo --integrate-existing --memory-only
design-intelligence contract validate --input work/design-contract.json
design-intelligence registry scan --root /path/to/repo
design-intelligence baseline request --root /path/to/repo --scenario surface --product Product --qa-report qa-report.json --model-review model-review.json --candidate-root screenshots/surface --requested-by agent:codex --output baseline-request.json
design-intelligence baseline request-audit --root /path/to/repo --input baseline-request.json
design-intelligence baseline decide --root /path/to/repo --request baseline-request.json --decision human-decision.json --output review-receipt.json
design-intelligence baseline receipt-audit --root /path/to/repo --input review-receipt.json
design-intelligence baseline lifecycle --root /path/to/repo
design-intelligence baseline preflight --root /path/to/repo --receipt review-receipt.json
design-intelligence baseline audit --root /path/to/repo
design-intelligence quality --input artifacts/design/reports/surface/qa-report.json --thresholds .design/quality/thresholds.json
design-intelligence repair --root /path/to/repo --plan repair-plan.json --evidence qa-report.json --iteration 1 --apply
design-intelligence self-audit --root /path/to/repo
design-intelligence agentic capsule --root /path/to/repo --input work/authority-capsule-input.json --output work/authority-capsule.json
design-intelligence agentic state-graph --input work/journey-state-input.json --output work/journey-state-report.json
design-intelligence agentic simulate --input work/counterfactual-input.json --output work/counterfactual-report.json
design-intelligence agentic arena --input work/design-arena-input.json --output work/design-arena-report.json
design-intelligence agentic outcome --input work/outcome-input.json --output work/outcome-assessment.json
design-intelligence agentic outcome-ratify --root /path/to/repo --assessment work/outcome-assessment.json --decision work/human-outcome-decision.json --output work/outcome-ratification.json
design-intelligence agentic outcome-ratification-audit --root /path/to/repo --input work/outcome-ratification.json
design-intelligence agentic outcome-promote --root /path/to/repo --receipt work/outcome-ratification.json
design-intelligence agentic outcome-retire --root /path/to/repo --input work/human-retirement-decision.json
```

For a mature repository, use the repository-finalization front door after the
governance map has been reviewed:

```bash
devctl program status --root /path/to/repo
devctl program plan --root /path/to/repo
devctl program complete --root /path/to/repo
```

`status` explains the governing model, user journey, architecture and
intelligence readiness, design gate, and whole backlog in product language.
`plan` exposes dependency-ordered waves without executing repository commands.
`complete` fails unless every control gate passes and every completion-governed
item has evidence-backed terminal status. See
`docs/REPOSITORY-FINALIZATION-PROGRAM.md`.

All commands remain read-only unless an explicit output path, registry `--write`, baseline review `request`, baseline `promote`, outcome ratification/promotion/retirement, or repair `--apply` is supplied. Outcome promotion and retirement append only to the existing canonical memory ledgers; they never replace history. A baseline review request writes only its declared request file.

The quoted task is the simplest front door. It defaults to the current repository and is equivalent to `start "<task>"`. The older `start /path/to/repo "<task>"` form remains compatible. Startup returns repository context, surface mode, direction briefs, reference ledger, proof gate, and an agent handoff. It writes only with `--save`, `--save-to`, `--contract-out`, or `--output`.

The recommended direction is deliberately not automatic approval. Run again with `--direction recommended` or a named direction ID after reviewing the options. This is the boundary between design research and implementation.

`work` organizes a material design task into a repository-aware contract, evidence-discovery plan, and explicit next action. It writes a contract only with `--contract-out`. `handoff` turns that plan into a compact Codex or Claude instruction packet and writes only with `--output`.

Use `start` when you do not want to remember the workflow shape. Use `work` and `handoff` separately only when you want to inspect or save the intermediate plan in more detail.

For an established repository, initialize only the institutional-memory files with
`memory init --integrate-existing --memory-only`. Then replace the package defaults
with repository-specific `product-rules.json` entries. An index-only rules file binds
every summarized rule to a canonical repository authority in `sourceAuthorities`;
memory audit and adoption both fail closed if a source is missing or its SHA-256 hash
changes. This keeps the repository documents authoritative and prevents memory setup
from installing a parallel quality or baseline system.

## Rendered QA

Install the optional pinned browser runtime:

```bash
npm install
npx playwright install chromium firefox webkit
```

Run the governed fixture proof:

```bash
npm run design:qa
npm run design:qa:cross-browser
npm run design:repair:prove
```

The reusable scenario format is demonstrated in `tests/design/scenarios/design-department-surface.json`. A consuming repository can provide `baseURL` for its existing server or `staticRoot` for a bounded static surface. The harness never starts arbitrary scenario shell commands. Cross-browser reports isolate artifacts by engine. Existing manifest `viewports` are treated as Chromium baselines only; Firefox and WebKit require separately approved `browsers.<engine>.viewports` entries, and otherwise produce structural evidence with visual comparison marked `NOT_RUN`.

## CI tiers

```bash
npm run design:ci:quick
npm run design:ci:standard
npm run design:ci:full
```

- `quick`: unit/governance tests, repository convergence, contracts, memory, baselines, registry, and diff hygiene
- `standard`: quick plus five-viewport Chromium scoring, isolated Chromium/Firefox/WebKit evidence, and an integrated evidence pack
- `full`: standard plus three rendered repair cycles, dependency audit, five skill validators, and self-audit

Legacy compatibility entry points still exist:

```bash
design-intelligence-inspect --root /path/to/repo
design-intelligence-assess --root /path/to/repo
```

## Skill installation

Codex:

```bash
./scripts/install
```

Use `./scripts/install-codex-skills` only when the CLI is already installed and just the skill files need refreshing.

Claude:

```bash
./scripts/install-claude-skills
```

Both scripts accept an optional destination path.

## Architecture

See [docs/ARCHITECTURE.md](/home/administrator/design-intelligence/docs/ARCHITECTURE.md).

Key design decisions:

- `design_intelligence/` is the vendor-neutral core package.
- `repo_fit/` remains as a compatibility wrapper for the older V0.1 entry points.
- Product archetypes are data-backed profiles, not hard-coded logic branches spread across the codebase.
- Read-only by default. Evidence output only writes when an explicit output path is supplied.

## Validation

Run the full test suite:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Validate the skills:

```bash
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/design-language
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/ux-architect
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/reference-intelligence
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/visual-review
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/design-linter
```

## Release

`VERSION`, `pyproject.toml`, `package.json`, `package-lock.json`, and package exports are aligned at `5.0.1`. The current patch release report is `docs/RELEASE-REPORT-5.0.1.md`; the V5 capability report remains `docs/RELEASE-REPORT-5.0.0.md`.
