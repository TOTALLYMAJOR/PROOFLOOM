# QuietPilot Architecture Adoption Report

Date: 2026-08-27
Scope: Compare `/home/administrator/projects_new/design-intelligence` with `/home/administrator/QP/QuietPilot` and identify shared architecture patterns plus adoption candidates for Design Intelligence.

## Executive Summary

Design Intelligence and QuietPilot already share the same governing philosophy: preserve repo-native authority, make proof boundaries explicit, keep generated artifacts subordinate to canonical sources, and block claims that outrun evidence.

The strongest adoption opportunity is not copying QuietPilot's product architecture into Design Intelligence. QuietPilot is a production SaaS monorepo; Design Intelligence is the reusable governance, design, and evidence utility. The right move is to extract QuietPilot's mature product-repo operating patterns into generic Design Intelligence capabilities:

1. Claim-boundary registries for any stateful repository, not only visual design.
2. Route/service/source-of-truth maps as first-class adoption evidence.
3. Workstream and outcome-contract fields inside task packets.
4. Capability-impact accounting tied to backlog, tests, and release evidence.
5. Proof-safe readiness wording that separates local checks, hosted/provider proof, human acceptance, release readiness, and production outcomes.

## Current Repo Shapes

### Design Intelligence

Observed shape:

- 486 tracked files.
- 31 tracked Python files under `design_intelligence/`.
- 17 JSON schemas under `design_intelligence/data/schemas/`.
- 96 tracked Markdown docs.
- 79 tracked test or fixture files under `tests/`.
- 5 checked-in repository skills.

Architectural role:

- Vendor-neutral utility package and CLI.
- `devctl` control-plane facade.
- Governance convergence, intent, architecture, intelligence, design, memory, and backlog auditors.
- Static architecture impact graph.
- Design evidence, adoption reports, memory preflight, and bounded repair.
- Explicit authority model: current user requirement, existing repo governance, existing architecture/design authorities, existing implementation patterns, then Design Intelligence guidance.

Design Intelligence already states that consuming repositories outrank package defaults, that runtime migration and knowledge migration are separate, and that `devctl` must index existing authority rather than install a competing system.

### QuietPilot

Observed shape:

- 2,599 tracked files.
- 705 tracked Markdown docs.
- 275 tracked Next.js `page.tsx` or route-handler files under `apps/web/app`.
- 394 tracked package source files under `packages/*/src`.
- 668 tracked test files matching repository test patterns.
- 20 accepted or tracked ADRs under `docs/architecture/adr`.

Architectural role:

- Product monorepo for a multi-organization, multi-workspace service revenue workflow platform.
- Next.js app in `apps/web`.
- Async worker in `apps/worker`.
- Modular packages: `contracts`, `domain`, `application`, `infrastructure`, `db`, and `vertical-packs`.
- Canonical commercial lifecycle: `Inquiry -> Lead -> Quote -> Proposal -> Customer Acceptance -> Payment -> Job Readiness -> Downstream Sync`.
- Product proof boundaries for transaction, payment, readiness, hosted provider, customer-token, partner staffing, AI, and demo/sample claims.

QuietPilot is more mature as a product-operating repository. Its strongest design is not the Next.js stack; it is the disciplined connection between source-of-truth records, route/service maps, proof wording, capability impact, validation scripts, and owner-visible readiness.

## What We Share

### 1. Repository Authority Comes First

Design Intelligence:

- Existing repository governance outranks package defaults.
- `.dev/` is an index and task packet store, not replacement product authority.
- Generated maps are hash-bound evidence and fail closed on drift.

QuietPilot:

- `AGENTS.md`, governance docs, backlog files, architecture docs, capability references, API snapshots, runbooks, and scripts form a priority-ordered authority chain.
- Historical audits and retired control-plane notes are evidence only.
- UI/design governance is repo-native and must not be replaced by a parallel design authority tree.

Shared lesson:

Design Intelligence should keep treating adoption as authority binding, not framework installation.

### 2. Proof Boundaries Prevent False Completion

Design Intelligence:

- Adoption reports distinguish recommendation from approval.
- `program complete` is not deployment, production acceptance, payment, or customer-outcome proof.
- Design repair cannot change baselines, thresholds, backend paths, tests, or architecture boundaries.

QuietPilot:

- The proof-boundary registry defines required evidence, allowed wording, forbidden wording, affected surfaces, visibility notes, tests/guards, and risk for claims.
- The transaction surface standard requires every stateful surface to explain stage, known truth, missing proof, proof boundary, owner, next action, and forbidden inference.

Shared lesson:

Design Intelligence already has the principle. QuietPilot has the stronger artifact format. Adopt the format generically.

### 3. Source Of Truth Is Explicit

Design Intelligence:

- Intent records are source-bound and SHA-256 bound.
- Architecture profiles cite authority paths, contract paths, standards, impact graph rules, owners, security boundaries, and journey bindings.
- Backlog completion requires terminal disposition across every completion-governed source.

QuietPilot:

- Product state is tied to explicit source-of-truth entities such as `QuoteVersion`, `ConfigVersion`, `ApprovalDecision`, `AcceptanceRecord`, `Job`, and `IntegrationJob`.
- Route handlers delegate to application services; domain modules own deterministic rules; infrastructure owns concrete adapters.
- Provider dashboards do not own commercial truth.

Shared lesson:

Design Intelligence should expand its generic source-binding model beyond documents and files into "claim authorities" and "state authorities" that consuming repos can declare.

### 4. Static Maps Support Bounded Work

Design Intelligence:

- Architecture graph asks what downstream code, contracts, journeys, tests, owners, and protected boundaries a changed path touches.
- It produces static evidence and required checks without executing commands automatically.

QuietPilot:

- Current codebase inventory maps apps, packages, route families, services, domain areas, adapters, persistence, and workers.
- Current route/service map connects routes to services and helper seams.
- Boundary scripts check command/query boundaries, AI advisory boundaries, workspace cache boundaries, route permissions, route policy coverage, hosted gates, and proof-boundary wording.

Shared lesson:

Design Intelligence's static graph is the right foundation. QuietPilot shows the missing higher-level projection: route/service/source maps that humans and agents can read before editing.

### 5. Human Gates Are Productive, Not Friction

Design Intelligence:

- Human direction selection is required before implementation handoff.
- Human receipts, baselines, quality thresholds, and architecture/proof boundaries can stop automation.

QuietPilot:

- Owner decisions, human visual acceptance, provider proof, release readiness, production readiness, and outcome review are separate authorities.
- Task packets require human approval checkpoints and blocked conditions.

Shared lesson:

Design Intelligence should make approval checkpoint types first-class so reports can say exactly which owner decision is missing.

## What Design Intelligence Can Adopt

### Adopt Now

1. Generic proof-boundary registry schema. Started in this repo.

QuietPilot's registry is currently product-specific, but the structure is reusable:

- claim
- required evidence/source
- allowed wording
- forbidden wording
- affected surfaces
- visibility notes
- tests or guards
- risk if violated

Design Intelligence now has the first neutral contract at `design_intelligence/data/schemas/claim-boundary-registry.schema.json`, documented in `docs/CLAIM-BOUNDARY-REGISTRY.md`, with a fixture at `tests/fixtures/claim-boundary-registry.json`. Consuming repos can use the same structure to declare claim families like transaction state, hosted readiness, AI authority, customer access, release readiness, data migration, or design approval.

2. Transaction-surface pattern as a "stateful surface contract."

The reusable version should apply to any workflow surface:

- stage
- known truth
- missing or blocked proof
- applicable boundary
- next-action owner
- next action route or command
- forbidden inference

For Design Intelligence, this would improve reports for product workflows, onboarding, AI review queues, release dashboards, and governance control panels.

3. Workstream and outcome-contract fields in task packets.

QuietPilot's required packet fields should inform Design Intelligence task-packet schema upgrades:

- objective and non-goals
- actor outcome
- success signal and check window
- evidence or assumption
- primary workstream
- reviewer workstream
- touched surfaces
- sequencing risks
- validation commands
- capability impact
- inventory or snapshot updates
- human approval checkpoints
- blocked conditions

Design Intelligence already has task packets and backlog semantics. This adoption would make task packets more owner-visible and less implementation-only.

4. Capability-impact accounting.

QuietPilot requires every meaningful change to update capability sources or declare `no capability delta`.

Design Intelligence should add this to backlog/program reporting:

- changed capability
- capability authority path
- status before/after
- evidence required
- whether docs, route maps, contract snapshots, or inventories must update

This would prevent "work completed" reports that do not update the consuming repo's product truth.

5. Proof-safe report language taxonomy.

Design Intelligence should standardize report labels for:

- local implementation
- local validation
- generated evidence
- hosted/provider proof
- human acceptance
- release readiness
- production readiness
- customer/business outcome

QuietPilot repeatedly benefits from keeping these separate. Design Intelligence can make that separation a reusable reporting convention.

### Adopt Next

6. Route/service/source-of-truth inventory adapter.

QuietPilot's `current-route-service-map.md` and `current-codebase-inventory.md` are manually readable architecture maps. Design Intelligence's architecture graph could generate a neutral draft for frameworks it recognizes:

- routes/pages
- command handlers
- query handlers
- services
- domain modules
- persistence/adapters
- provider seams
- tests
- protected boundaries

This should be an evidence draft, not canonical architecture unless the consuming repo promotes it.

7. Boundary-check registry.

QuietPilot's scripts make boundaries executable: command/query, proof wording, route permissions, workspace isolation, hosted gates, migration rationale, AI advisory boundaries.

Design Intelligence can generalize this as:

- boundary id
- path patterns
- forbidden imports or claims
- required check command
- owner authority
- severity
- exception path

The existing architecture graph `securityRules` is close. It should grow from protected-path checks into reusable boundary classes.

8. Advisory AI boundary model.

QuietPilot has a mature model for AI: advisory, review-only, feature-gated, source-referenced, and prohibited from mutation paths.

Design Intelligence can adopt this as a generic "AI authority boundary" that consuming repos can bind:

- advisory contract required
- source references attached by the app or validated data, not invented by the model
- kill switch or feature resolution required
- no imports from mutation, transaction, repository-write, provider, or infrastructure clients
- accepted/rejected/adjusted review outcomes only

This fits Design Intelligence's intelligence-routing plane well.

9. Hosted/provider evidence gates.

QuietPilot separates local config, provider dashboard state, webhook proof, hosted route behavior, and production readiness.

Design Intelligence should add a provider-proof vocabulary to program status so consuming repos can declare:

- local-only evidence
- preview evidence
- production deployment evidence
- provider API evidence
- webhook/callback evidence
- redacted runbook evidence
- missing proof

### Do Not Adopt Directly

1. Do not copy QuietPilot's Commercial Spine as a generic product model.

It is excellent for QuietPilot but too domain-specific for Design Intelligence. Adopt the idea of a canonical lifecycle, not this lifecycle as a package default.

2. Do not copy Next.js or package layout assumptions.

QuietPilot's `apps/web`, `apps/worker`, and `packages/*` structure is useful evidence for a SaaS modular monolith. Design Intelligence must remain framework-neutral.

3. Do not make QuietPilot docs canonical inside Design Intelligence.

QuietPilot should remain a profile, fixture, pilot, or example. Its product decisions should not become Design Intelligence authority.

4. Do not auto-generate active backlog truth from QuietPilot's model.

Design Intelligence should inventory and validate backlog authority. It should not promote, rewrite, or complete consuming repo work without owner approval.

## Recommended Adoption Roadmap

### Phase 1: Claim Boundary Foundation

Status: started.

Added:

- `claim-boundary-registry.schema.json`
- neutral fixture and focused schema-shape test
- `docs/CLAIM-BOUNDARY-REGISTRY.md`

Still open:

- parser/auditor for claim boundaries
- generic report section for allowed wording, forbidden wording, missing proof, and required guards
- tests using QuietPilot-like fixtures

Expected benefit:

Design Intelligence can evaluate whether a repo's docs, UI copy, task packet, or release note is overclaiming.

### Phase 2: Stateful Surface Contracts

Add:

- `stateful-surface-contract.schema.json`
- detection/report support in `devctl program status`
- fields for stage, known truth, missing proof, owner, next action, and forbidden inference

Expected benefit:

User-facing workflow work stops being treated as just component/layout work. The report can flag when a surface lacks owner/action/proof clarity.

### Phase 3: Task Packet Upgrade

Extend task packets with:

- actor outcome
- success signal/window
- evidence-or-assumption
- primary/reviewer workstreams
- capability impact
- approval checkpoints
- inventory/snapshot update obligations

Expected benefit:

Design Intelligence can produce agent-ready packets with stronger closeout criteria and fewer false "done" states.

### Phase 4: Architecture Inventory Projection

Extend architecture graph output into optional readable maps:

- codebase inventory
- route/service map
- command/query split
- provider seam map
- protected-boundary map

Expected benefit:

Consuming repos get QuietPilot-style architecture visibility without manually creating long inventory documents.

### Phase 5: Provider And AI Authority Boundaries

Add reusable boundary packs:

- hosted/provider proof
- AI advisory/review-only authority
- customer/public access grants
- payment/subscription or external truth boundaries

Expected benefit:

Design Intelligence becomes more useful for real production SaaS repositories without becoming product-specific.

## Highest-Leverage Next Action

Start with the claim-boundary registry. It is the cleanest transfer from QuietPilot because it is:

- already proven useful in a mature repo;
- generic enough for any stateful product;
- aligned with Design Intelligence's existing proof-boundary and adoption-gate philosophy;
- cheap to test with fixtures;
- useful before any runtime integration.

The first implementation slice is now documentation plus schema plus tests, not runtime mutation:

1. Added `design_intelligence/data/schemas/claim-boundary-registry.schema.json`.
2. Added a fixture modeled on QuietPilot's registry structure but with neutral claims.
3. Next: add an auditor that validates required evidence, allowed/forbidden wording, affected surfaces, guard paths, and risk fields.
4. Next: surface the result in `devctl planes audit` or `devctl program status`.
5. Keep QuietPilot as a product-profile example, not as package authority.

## Evidence Read

Design Intelligence sources inspected:

- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/CONTROL-PLANE-INTENT-ARCHITECTURE-INTELLIGENCE.md`
- `docs/CONTROL-PLANE-ARCHITECTURE-GRAPH.md`
- `docs/REPOSITORY-FINALIZATION-PROGRAM.md`
- `docs/DESIGN-MEMORY-PREFLIGHT.md`
- `devctl.yaml`
- `package.json`
- `design_intelligence/adoption.py`
- `design_intelligence/planes.py`
- `design_intelligence/architecture_graph.py`
- `design_intelligence/data/schemas/backlog-portfolio.schema.json`

QuietPilot sources inspected:

- `AGENTS.md`
- `package.json`
- `docs/governance/README.md`
- `docs/backlog-governance.md`
- `docs/product/platform-specification.md`
- `docs/product/proof-boundary-registry.md`
- `docs/product/transaction-surface-standard.md`
- `docs/architecture/module-boundaries.md`
- `docs/architecture/command-query-boundaries.md`
- `docs/architecture/adr/0001-modular-monolith.md`
- `docs/architecture/adr/0002-source-of-truth-boundaries.md`
- `docs/architecture/revenue-platform/03-codex/current-codebase-inventory.md`
- `docs/architecture/revenue-platform/03-codex/current-route-service-map.md`

Boundary note: Memory was used only to route inspection and recover known QuietPilot risk areas. Current-source inspection controlled the report conclusions.
