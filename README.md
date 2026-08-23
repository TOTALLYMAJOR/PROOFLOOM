# Design Intelligence v3.0.0

Design Intelligence is a production-grade, vendor-neutral utility for repository-aware design work. Its core mission is design intelligence: understand product intent, preserve existing design truth, reason about UX and design-system change, validate rendered outcomes, and record evidence without turning into a second application scaffold.

The governing objective is:

> Product intent -> repository evidence -> design reasoning -> implementation constraints -> rendered validation -> design learning.

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
design-intelligence assess --root /path/to/repo
design-intelligence context --root /path/to/repo --profile quotepilot
design-intelligence lint --root /path/to/repo
design-intelligence refactor-risk --root /path/to/repo
design-intelligence review --input work/review-manifest.json
design-intelligence validate --root /path/to/repo --review-input work/review-manifest.json --evidence-pack-out work/evidence-pack.md
design-intelligence doctor --root /path/to/repo
design-intelligence work --root /path/to/repo --task "Improve proposal comparison" --profile quotepilot
design-intelligence handoff --root /path/to/repo --task "Improve proposal comparison" --profile quotepilot --reference https://aura.build --output work/handoff.md
design-intelligence memory context --root /path/to/repo --product quotepilot --surface QuoteWorkspace --component QuoteSidebar
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
```

All commands remain read-only unless an explicit output path, registry `--write`, baseline review `request`, baseline `promote`, or repair `--apply` is supplied. A baseline review request writes only its declared request file.

The quoted task is the simplest front door. It defaults to the current repository and is equivalent to `start "<task>"`. The older `start /path/to/repo "<task>"` form remains compatible. Startup returns repository context, surface mode, direction briefs, reference ledger, proof gate, and an agent handoff. It writes only with `--save`, `--save-to`, `--contract-out`, or `--output`.

The recommended direction is deliberately not automatic approval. Run again with `--direction recommended` or a named direction ID after reviewing the options. This is the boundary between design research and implementation.

`work` organizes a material design task into a repository-aware contract, evidence-discovery plan, and explicit next action. It writes a contract only with `--contract-out`. `handoff` turns that plan into a compact Codex or Claude instruction packet and writes only with `--output`.

Use `start` when you do not want to remember the workflow shape. Use `work` and `handoff` separately only when you want to inspect or save the intermediate plan in more detail.

## Rendered QA

Install the optional pinned browser runtime:

```bash
npm install
npx playwright install chromium
```

Run the governed fixture proof:

```bash
npm run design:qa
npm run design:repair:prove
```

The reusable scenario format is demonstrated in `tests/design/scenarios/design-department-surface.json`. A consuming repository can provide `baseURL` for its existing server or `staticRoot` for a bounded static surface. The harness never starts arbitrary scenario shell commands.

## CI tiers

```bash
npm run design:ci:quick
npm run design:ci:standard
npm run design:ci:full
```

- `quick`: unit/governance tests, contracts, memory, baselines, registry, and diff hygiene
- `standard`: quick plus five-viewport Playwright QA, deterministic scoring, and integrated evidence pack
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

`VERSION`, `pyproject.toml`, `package.json`, and package exports are aligned at `3.0.0`. The V3 release report is `docs/RELEASE-REPORT-3.0.0.md`.
