# Design Intelligence V3 Repository Guide

This repository owns the reusable utility itself. It does not outrank consuming repositories.

## Operating rules

- Design intelligence is the primary mission; repository intelligence is supporting infrastructure.
- Existing repository authorities outrank package defaults.
- Mature repositories must pass governance convergence before material design work begins.
- Map vision, actors, requirements, journeys, architecture, backlog, instructions, skills, hooks, and proof before proposing design.
- Preserve and bind an equally effective repository model instead of installing a competing control system.
- Read-only by default. Only write artifacts when an explicit output path or installation target is requested.
- `design-intelligence "<task>"` is the canonical front door; preserve its simple current-directory default.
- A recommended design direction is not approval. Implementation requires explicit direction selection.
- Supplied references remain `RESEARCH_REQUIRED` until observed patterns and transformations are recorded.
- Prefer knowledge alignment over runtime migration when it captures most of the value.
- Do not add a second component system, second token system, second backlog, or second E2E hierarchy.

## Map

- `design_intelligence/`: vendor-neutral core package and CLI
- `.design/memory/`: canonical append-oriented decision, outcome, exception, debt, and component records
- `.design/quality/`: governed deterministic thresholds and score history
- `.design/baselines/`: approval-bound visual baselines; never update silently
- `scripts/design/`: Playwright QA, repair proof, and tiered CI orchestration
- `tests/design/`: route-specific scenario definitions; do not create a parallel product E2E hierarchy
- `artifacts/design/`: contracts and generated evidence packs
- `repo_fit/`: V0.1 compatibility wrappers
- `skills/`: concise skills plus reference docs
- `templates/` and `examples/`: reusable design artifacts and product profiles
- `adapters/`: thin Codex and Claude adapter guidance
- `devctl.yaml` and `.dev/`: control-plane index, bounded task packets, hash-bound intent index, standards profile, and capability routing; never a second product, design, architecture, or backlog authority
- `.dev/governance/`: generated rehabilitation map, adapter, drift manifest, execution plan, human readout, and owner-ratification packet; never canonical product authority
- `docs/`: architecture and release notes
- `tests/fixtures/`: bounded proof repositories and manifests

## Validation

- Run `npm run design:ci:quick` for core and governance changes.
- Run `devctl validate` and `devctl doctor` after changing control-plane declarations or authorities.
- Run `devctl govern audit`, `devctl govern plan`, and `devctl govern verify` after changing critical product understanding or governance.
- Run `devctl planes audit`, `devctl backlog status`, and `devctl health` after changing intent, journeys, standards applicability, intelligence routing, or backlog sources.
- Never claim backlog completion from a partial queue. Every declared completion-governed item must have a valid terminal disposition.
- Run `npm run design:ci:standard` for material rendered changes.
- Run `npm run design:ci:full` before a release.
- Run the skill validator for each skill before tagging.
- Keep `VERSION`, `pyproject.toml`, and `design_intelligence/__init__.py` aligned.
- Automatic repair stops after 3 iterations or at authority, scope, architecture, baseline, threshold, test, backend, or product-behavior boundaries.
