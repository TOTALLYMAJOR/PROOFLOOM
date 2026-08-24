# Development Control Plane Phase 4

## Outcome

Phase 4 adds repository-governed Intent, Architecture, and Intelligence planes to the existing Phase 0-3 control-plane facade.

```text
repository authorities
  -> intent, personas, requirements, journeys, metrics
  -> complete backlog inventory and dependency waves
  -> contextual official-standards profile
  -> vendor-neutral capability routing
  -> bounded context and affected verification
  -> existing Design Intelligence and Playwright evidence
```

The control plane still does not merge, deploy, mutate baselines, weaken thresholds, bypass architecture boundaries, or treat model output as repository authority.

## Intent and journeys

`.dev/intent-index.json` is a hash-bound index into canonical repository documents. It includes vision, principles, personas, requirements, journeys, success metrics, constraints, and experiments. The index is not the canonical product document.

Every active record has an owner-reviewed date and a source path plus SHA-256 identity. Every active journey has an owner, personas, requirements, starting state, success state, tests, metrics, and review date. Active requirements must have reciprocal journey coverage. User-facing task packets must link requirements, journeys, and success metrics.

## Whole-backlog completion

`devctl backlog status` parses every declared completion-governed source. `devctl backlog plan` emits dependency waves containing every open item as ready, blocked, staged, or waiting on dependencies. `devctl backlog complete` is the strict mission/release gate and fails until the entire governed portfolio is terminal.

Backlog integrity fails for missing sources, parser failures, duplicate active IDs, unknown statuses, missing dependencies, cycles, completed items without evidence, or cancelled/deferred items without authority and rationale. Backlog completion is `COMPLETE` only when every governed item is `COMPLETED`, `CANCELLED`, or `DEFERRED_WITH_AUTHORITY` and all terminal evidence rules pass.

This definition governs the entire declared backlog, not only the next work slice. It does not mean blocked or human-gated work is executed without authority. Integrity checks belong in normal CI; the strict completion gate belongs at an explicit mission or release boundary so an honestly open backlog does not block every incremental change.

## Architecture currency

`.dev/standards-profile.json` records repository contexts, applicability, disposition, rationale, evidence, and review dates against `design_intelligence/data/defaults/industry-standards.json`. The catalog stores official URLs and a review deadline. The audit fails stale versions, expired reviews, missing applicable entries, evidence gaps, or applicability mismatches.

The current catalog covers:

- NIST SSDF 1.1;
- WCAG 2.2;
- OWASP ASVS 5.0.0;
- SLSA 1.2;
- NIST AI RMF 1.0 and NIST AI 600-1;
- NIST CSF 2.0;
- OpenTelemetry Specification 1.60.0;
- ISO/IEC 25010:2023;
- ISO 9241-210:2019;
- OpenAPI 3.2.0.

The profile is a contextual engineering assessment. It is not a certification or a claim that every control in a referenced standard is implemented.

The Architecture plane also requires existing architecture authorities, contract files, at least one ADR match, declared boundary checks, and a dated technology-currency review. Technology currency uses the policy `contextual-not-latest`: dependency and runtime choices must be reviewed against repository constraints, lockfiles, audits, and supported upgrade paths rather than being upgraded merely because a newer version exists. Missing manifests, evidence, boundary commands, ADRs, or an expired technology review fail closed.

## Intelligence routing

`.dev/model-routing.json` defines capability classes by work type, risk, required capabilities, and priority. Provider and model names are forbidden. The current classes cover bounded context, architecture reasoning, visual evidence analysis, and cross-plane reasoning.

Major product decisions, architecture-boundary changes, security-policy changes, production writes, and governed-baseline mutations require human approval. High-risk and authority-bound task routes surface the same requirement.

## Adoption in another repository

1. Run read-only discovery:

   ```bash
   devctl init --dry-run --root /path/to/repository --format json
   ```

2. Review detected instructions, governance, product, architecture, design, backlog, and verification authorities. Remove historical or non-authoritative candidates rather than treating discovery as approval.
3. Run additive initialization. It creates only `devctl.yaml`, `.dev/VERSION`, and task-state directories.
4. Create repository-owned intent, standards, and routing files using the bundled schemas. Point records to existing canonical documents; do not duplicate them under `.dev/`.
5. Enable each reviewed plane in `devctl.yaml`.
6. Run `devctl validate`, `devctl planes audit`, `devctl backlog status`, and `devctl health`.
7. Create schema-version-2 task packets that link backlog items and, for user-facing work, requirements, journeys, and metrics.
8. Use bounded context, impact, route, and visual planning. Execute selected checks through the repository's existing CI or an authorized operator.

## QuietPilot boundary

The implementation has only been run against Design Intelligence's bounded existing frontend surface. QuietPilot was inspected read-only to verify that discovery can see repository governance, architecture, product, backlog, and package-script conventions. No QuietPilot file was changed and no QuietPilot readiness or backlog-completion claim is made.

## Commands

```bash
devctl discover --root /path/to/repository
devctl validate --root /path/to/repository
devctl planes audit --root /path/to/repository
devctl backlog status --root /path/to/repository
devctl backlog plan --root /path/to/repository
devctl backlog complete --root /path/to/repository
devctl health --root /path/to/repository
devctl intelligence route TASK-ID --root /path/to/repository
devctl task context TASK-ID --root /path/to/repository
devctl verify affected TASK-ID --root /path/to/repository --changed src/App.tsx
```

## Failure injection

The test suite proves fail-closed behavior for stale standards reviews, vendor-bound routing, active journeys without tests, duplicate backlog IDs, unproven completion, unauthorized cancellation or deferral, missing dependencies, and non-mutating discovery. Existing full CI continues to prove three rendered repair cycles, threshold floors, governed baselines, component registry integrity, evidence packs, and the five V1 skills.
