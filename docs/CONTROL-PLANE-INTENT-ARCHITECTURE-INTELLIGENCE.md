# Control Plane Intent, Architecture, and Intelligence Authority

## Authority and claim boundary

This document is the repository authority for the Design Intelligence development control plane's intent, user journeys, architecture constraints, and intelligence boundaries. It does not outrank a consuming repository. A consuming repository's approved governance, product intent, architecture decisions, backlog, design system, tests, and release controls remain authoritative.

The control plane may report evidence, gaps, dependency waves, and bounded plans. It may not claim certification, product acceptance, backlog completion, deployment, or production outcomes without the required repository evidence and human authority.

## Vision

Provide one repository-native control plane that connects product intent, architecture, intelligence, execution, design, evidence, memory, and delivery without creating competing sources of truth.

## Principles

1. Existing repository authority outranks package defaults.
2. User-facing work must link requirements, journeys, success metrics, tests, and evidence.
3. Backlog completion means every completion-governed item has an authoritative terminal disposition; it never means only the next items were attempted.
4. Industry currency is a dated applicability assessment against official sources, not an undated model assertion or certification claim.
5. Intelligence routing selects vendor-neutral capability classes. Product, architecture, security, production, and baseline authority remain human-gated.
6. Retrieval, execution, repair, and mutation stay bounded by declared scope and repository policy.

## Personas

### Repository owner

Needs a truthful view of what the repository is trying to accomplish, what remains open, what standards apply, and which decisions require approval.

### Consuming development team

Needs additive adoption that finds current authorities, scripts, journeys, architecture records, and backlog sources before proposing configuration.

### Product user

Needs frontend changes to preserve the intended starting state, decisions, success state, accessibility, and authoritative application behavior.

## Requirements

### REQ-ADOPTION-001 Repository-native adoption

Discovery must be read-only, identify repository authorities and verification commands, surface readiness gaps, and avoid generating product intent on the owner's behalf.

### REQ-JOURNEY-001 Journey-bound user-facing work

A user-facing task must reference active requirements, journeys, and success metrics. Each active journey must identify its owner, personas, starting state, success state, tests, metrics, and review date.

### REQ-BACKLOG-001 Whole-backlog accounting

Every item from every declared completion-governed backlog source must be parsed, uniquely identified, dependency-checked, and assigned a current or terminal state. `COMPLETE` is permitted only when all such items are terminal and terminal dispositions carry required evidence or authority.

### REQ-STANDARDS-001 Contextual standards currency

Architecture health must compare the repository's dated standards profile with the bundled official-source catalog, validate contextual applicability and evidence, fail expired or stale versions, and explicitly deny certification claims.

### REQ-ROUTING-001 Capability-based intelligence

Task routing must use work type, risk, and required capabilities. Routing policy must not bind to model vendors and must fail closed at product, architecture, security, production, and governed-baseline boundaries.

### REQ-VISUAL-001 Rendered design proof

The bounded Design QA Control Deck journey must preserve the existing design-memory, quality-threshold, Playwright, accessibility, DOM/state, baseline, and three-iteration repair authorities.

## User journeys

### JRN-ADOPT-001 Adopt into an existing repository

- Owner: consuming repository owner
- Personas: repository owner; consuming development team
- Starting state: the repository has its own instructions, architecture, product documents, backlog, scripts, and possibly design infrastructure.
- Journey: run read-only discovery; review detected authorities and gaps; map intent and journeys; assess applicable official standards; bind capability routing; validate the proposed manifest; approve additive installation; run health and failure-injection checks.
- Success state: the repository has one reviewed control-plane index that delegates to existing authorities and reports every backlog item without performing an unauthorized mutation.
- Tests: `tests/test_control_plane.py`; `tests/test_planes.py`
- Metrics: complete discovery coverage; zero writes during dry-run; zero duplicate authority systems; all configured planes pass before readiness is claimed.

### JRN-PILOT-001 Validate the bounded Design QA Control Deck

- Owner: Design Intelligence maintainer
- Personas: repository owner; product user
- Starting state: a frontend fixture, governed five-viewport scenario, thresholds, baselines, design memory, and prior adoption evidence exist.
- Journey: load linked intent; select affected checks; render governed viewports; validate accessibility and DOM/state; score quality and drift; attempt only bounded deterministic repairs; stop after three iterations or an authority boundary; package evidence; record outcomes.
- Success state: deterministic quality and governance audits pass without threshold weakening or baseline mutation, and the evidence pack remains linked to the task and journey.
- Tests: `tests/design/scenarios/design-department-surface.json`; `tests/test_control_plane.py`; `tests/test_governance_v3.py`
- Metrics: five governed viewports; quality score at or above the existing threshold; zero unauthorized baseline changes; exactly three proven repair cycles in the repair proof.

## Success metrics

### MET-ADOPTION-001 Safe discovery

Dry-run adoption writes zero files and inventories current repository authorities, verification commands, backlog candidates, and plane readiness gaps.

### MET-JOURNEY-001 Journey coverage

Every active user-facing requirement has reciprocal active-journey coverage, each active journey has at least one existing test, and user-facing task packets contain journey links.

### MET-BACKLOG-001 Portfolio truth

One hundred percent of declared completion-governed backlog items appear in status and dependency-wave evidence; no unparsed or duplicate active item is accepted.

### MET-STANDARDS-001 Current contextual assessment

Every catalog standard is dispositioned according to repository context, applicable entries cite existing repository evidence, and review expiry fails closed.

### MET-ROUTING-001 Governed routing

Every valid task resolves to one approved vendor-neutral capability class or fails closed; high-risk and authority-bound work requires human approval.

### MET-VISUAL-001 Existing visual quality threshold

The bounded pilot retains its governed quality score, baseline manifest hash, accessibility checks, DOM/state evidence, and repair ceiling without weakening thresholds.

## Architecture constraints

- `.dev/` is an index and task packet store, not a replacement product authority, design memory, backlog, architecture tree, or test hierarchy.
- Canonical source records are repository-relative and SHA-256 bound.
- Standards profiles record applicability and implementation evidence but never represent external certification.
- The control-plane facade plans affected commands; repository CI or an authorized operator executes them.
- Whole-backlog planning respects dependencies, blocked states, staged states, and human gates. It does not bypass them to satisfy a completion target.
- Design QA delegates to the existing Design Intelligence engine and governed Playwright hierarchy.

## Intelligence boundaries

Capability routing may distinguish bounded context analysis, deterministic governance, architecture reasoning, and visual evidence analysis. It must not encode vendor or model names. Product strategy, major UX direction, irreversible architecture, security and data policy, production writes, deployment, billing, identity and access changes, and governed baseline mutation require human approval.

## Industry standards assessment boundary

The bundled catalog uses official references for NIST SSDF, WCAG, OWASP ASVS, SLSA, NIST AI RMF and its Generative AI Profile, NIST CSF, OpenTelemetry, ISO/IEC 25010, ISO 9241-210, and OpenAPI. Repository profiles must record current versions, context-based applicability, rationale, evidence, and a review deadline. Standards with licensing restrictions are referenced only at the public metadata level; the package does not reproduce licensed requirements.

## Backlog completion semantics

Valid terminal states are `COMPLETED`, `CANCELLED`, and `DEFERRED_WITH_AUTHORITY`. Completed items require evidence. Cancelled and authority-deferred items require an identified authority and rationale. Active, blocked, staged, unknown, duplicated, unparsed, cyclic, or missing-dependency items prevent a `COMPLETE` claim.
