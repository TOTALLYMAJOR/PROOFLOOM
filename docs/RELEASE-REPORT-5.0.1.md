# Design Intelligence 5.0.1 Release Report

## Outcome

V5.0.1 packages the post-V5 adoption-evidence portability correction already validated on `main`.

## Delivered

- adoption-report audit now distinguishes a legitimate checkout relocation from source or authority tampering
- immutable recorded repository provenance remains present in the report identity
- all relative source and authority hashes remain mandatory
- audit output records relocation through `checkoutRelocated`, `recordedRepositoryRoot`, and warnings
- relocation, source-tampering, and authority-tampering regression coverage remains fail-closed
- the current hash-bound adoption authority is `artifacts/design/adoptions/preserve-evidence-first-design-qa-hierarchy-v11/adoption-report.json`; V9 and V10 remain immutable historical evidence

## Boundaries Preserved

- a relocated checkout is not trusted merely because its path differs
- source and authority content must still exactly match the adoption report
- design baselines, thresholds, product code, and consuming repositories are not changed
- no baseline promotion, repair application, deployment, or external provider write is performed

## Validation Required for Release

- `npm run design:ci:quick`
- `npm run design:ci:standard`
- `npm run design:ci:full`
- remote CI must pass all three corresponding jobs on the release commit

## V6 Handoff

V6 planning is recorded in `docs/ROADMAP-V6-RUNTIME-OUTCOMES.md`. It is a proposed next phase and grants no runtime, deployment, or mutation authority.
