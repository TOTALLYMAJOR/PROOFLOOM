# Design Intelligence V3 Architecture With Adoption Gate

## Mission front door

```text
plain-English task -> repository context -> inferred surface mode -> three direction briefs
                   -> explicit direction selection -> implementation handoff -> rendered proof
```

`design-intelligence "<task>"` is read-only and defaults to the current repository. It produces a recommendation but blocks implementation until a direction is explicitly selected. `--save` writes only a generated mission bundle under `artifacts/design/missions/`.

The reference ledger is evidence, not authority. A supplied URL or `DESIGN.md` begins as `RESEARCH_REQUIRED`; it cannot become an imported visual direction without observed patterns, product relevance, original transformation, and explicit rejection notes.

Reference-backed missions add a fail-closed gate between direction selection and implementation:

```text
site/images -> Playwright or local-byte evidence -> typed semantic adapter
            -> repository/backlog/hooks/instructions/design-system/memory reconciliation
            -> governed human receipt reconciliation -> deterministic adoption report
            -> existing design contract -> mission handoff
```

The adapter may observe and recommend. It cannot authorize a product capability, assert absence without bound repository-search evidence, override repository authority, lower quality thresholds, mutate a baseline, or select the final adoption decision. Named product profiles fail closed when institutional memory is unavailable. Supplied human lifecycle receipts are replay-audited and remain authoritative over implementation readiness.

## Governed cycle

```text
request -> relevant memory -> design contract -> implementation -> Playwright render
        -> screenshot + DOM/state + axe -> visual review -> design linter
        -> deterministic quality gates -> memory outcome
                                      \-> bounded repair -> rerender (max 3)
```

Model review can classify hierarchy, workflow, visual, responsive, accessibility, component, or drift defects. It cannot modify deterministic scores, lower thresholds, update baselines, or promote its own opinion into institutional law.

## Development control-plane facade

Phases 0-3 add `devctl` as a repository coordination facade, not another intelligence product:

```text
devctl.yaml -> task packet -> trust-ranked bounded context -> affected verification plan
                                                    \-> existing design/adoption/visual auditors
```

`devctl.yaml` indexes existing instructions, architecture, verification commands, and Design Intelligence authorities. `.dev` stores only the manifest version and task packets. `.design`, existing Playwright scenarios, product backlogs, component systems, and release controls remain canonical. The facade does not execute arbitrary commands in this phase. See `docs/CONTROL-PLANE-PHASES-0-3.md` and ADR-0001.

Phase 4 extends the same facade with three governed projections:

```text
Intent       -> source-bound vision, personas, requirements, journeys, metrics, experiments
Architecture -> contextual official-standards versions, applicability, evidence, and expiry
Intelligence -> instruction/skill inventory and vendor-neutral capability routing
```

The intent index points to canonical repository documents by path and SHA-256. It does not become canonical product truth. The backlog portfolio inventories every declared completion-governed source and permits `COMPLETE` only when every item has a valid terminal disposition. The standards profile is a dated engineering assessment, never certification. Capability routing cannot cross product, architecture, security, production, or baseline authority boundaries. See `docs/CONTROL-PLANE-PHASE-4.md` and ADR-0002.

## Core shape

`design_intelligence/` is the vendor-neutral core package.

It owns:

- bounded repository discovery
- scaffold reconciliation
- migration-risk scoring
- context generation
- reference transformation
- deterministic design linting
- visual-review aggregation
- validation and evidence packs
- conservative doctor / repair planning
- scoped institutional memory and provenance
- governed baseline promotion and integrity auditing
- deterministic quality and drift scoring
- exact bounded repair execution
- V2 self-audit
- V3 surface-mode inference, direction briefs, reference ledger, and rendered-proof mission gate
- evidence-bound reference capture and deterministic design adoption/refusal

`repo_fit/` remains as a compatibility layer for V0.1 entry points.

## Authority model

Design Intelligence does not become the new repository authority by default.

Established products use index-only institutional memory. The memory rules summarize
canonical repository authorities and bind each source by repository-relative path and
SHA-256; they do not migrate or supersede those authorities. Source drift invalidates
memory retrieval and blocks adoption until a reviewer reconciles and reindexes the
changed authority. Memory-only initialization deliberately omits quality thresholds
and baseline infrastructure so integration cannot create a competing QA system.

Priority order:

1. current user requirement
2. existing repository governance
3. existing architecture and design authorities
4. existing tokens, components, and implementation patterns
5. Design Intelligence guidance

## Read-only default

Every CLI command is read-only unless the user explicitly requests an output path or installation target.

Examples:

- `validate --evidence-pack-out ...` writes an evidence artifact
- install scripts copy skills into Codex or Claude skill directories

The utility does not silently mutate consuming repositories.

## Migration boundaries

Two migrations are scored separately:

- knowledge migration: docs, decisions, indexes, AGENTS navigation
- runtime migration: components, imports, package boundaries, filesystem structure

The default preference is 80/20 alignment:

- keep runtime structure
- converge duplicate authorities
- add only missing design capability

## Product archetypes

QuotePilot, QuietPilot, and LeaguePilot are data-backed product profiles.

They live outside the reasoning code as package data and human-readable examples so the core remains vendor-neutral.

## Evidence model

Material design work can produce an evidence pack containing:

- contract
- repo context
- before and after screenshots
- lint and accessibility findings
- visual-review findings
- decision summary
- remaining debt

This is a Git-friendly record, not a second dashboard or backlog.

## Canonical authorities

- `.design/memory/*.jsonl` owns append-oriented decisions, outcomes, exceptions, and debt.
- `.design/memory/product-rules.json` owns inherited portfolio, archetype, and product rules.
- `.design/memory/component-registry.json` is a generated source registry enriched with existing metadata.
- `.design/quality/thresholds.json` owns measurable quality gates.
- `.design/baselines/manifest.json` owns baseline hashes and approval provenance.
- `docs/design/*.md` explains these authorities but is not a second ledger.

## Repair boundary

`repair --apply` performs only an exact text substitution when all of these are true:

- a P0, P1, or clear P2 finding ID exists in supplied evidence
- the target is explicitly allowlisted
- the expected text matches exactly once
- the plan declares `visual-only` authority
- the iteration is 1 through 3
- the target is not a baseline, threshold, test, migration, API, server, or backend path
- the plan has no architecture impact

Anything else returns `BLOCKED` without changing files.
