# Repository Finalization Program

## Purpose

The finalization program is the human-readable front door for a mature repository. It joins the existing governance scanner, intent index, user journeys, standards profile, architecture graph, intelligence routing, design authorities, repository verification, and the entire declared backlog. It does not install a second product model or hide unfinished work behind a short execution queue.

The program answers six questions in order:

1. What product and governing system does this repository currently declare?
2. Which user journey must the product complete, and where is its executable proof?
3. Which architecture, contracts, instructions, skills, and protected boundaries apply?
4. Which existing design system, memory, accessibility rules, and visual checks govern the surface?
5. What is every remaining backlog item, including blocked, staged, deferred, and dependency-bound work?
6. What evidence is required before implementation, completion, release, or outcome claims are permitted?

## Operating Sequence

```text
tracked repository evidence
  -> governance audit and derived convergence map
  -> intent, persona, requirement, journey, and metric bindings
  -> architecture currency and bounded impact graph
  -> vendor-neutral capability routing and authority stops
  -> repository-native design gate
  -> dependency-ordered whole-backlog task execution
  -> affected tests, browser QA, accessibility, DOM/state, and proof boundaries
  -> evidence-backed terminal disposition
  -> release and measured outcomes as separate authorities
```

## Commands

Run these from the Design Intelligence checkout or through an installed `devctl` link:

```bash
./scripts/design-intelligence govern audit --root /path/to/repository
./scripts/design-intelligence govern apply --root /path/to/repository
./scripts/devctl validate --root /path/to/repository
./scripts/devctl program status --root /path/to/repository
./scripts/devctl program plan --root /path/to/repository
./scripts/devctl program complete --root /path/to/repository
```

`govern apply` is the only automatic repository adaptation in this sequence. It writes derived, hash-bound navigation under `.dev/governance/` and never rewrites canonical vision, backlog, architecture, instructions, design, or runtime files.

`program status` returns the direct answer, mapped user journeys, governance stops, six program phases, whole-backlog counts, dependency waves, and the next authority-safe action.

`program plan` returns the same governed state as a whole-program plan. It does not execute arbitrary repository commands. A coding agent or human uses the repository's task packet, impact, and affected-verification commands for each approved item, then records completion evidence in the canonical backlog.

`program complete` is an assertion gate. It exits nonzero unless governance, intent, architecture, intelligence, design, verification, and all completion-governed backlog items pass. `COMPLETE` is not a deployment, production acceptance, payment, or customer-outcome claim.

## Adoption In Another Repository

1. Run `devctl init --dry-run --root /path/to/repository` to inventory current authorities and proposed bindings without writes.
2. Review the repository's existing `AGENTS.md`, hooks, skills, ADRs, product documents, journeys, backlogs, tests, design system, and release controls.
3. Add one `devctl.yaml` adapter plus `.dev/intent-index.json`, `.dev/standards-profile.json`, and `.dev/model-routing.json`. Bind existing systems rather than copying package defaults.
4. Use `spec.design.mode: repository-native` when the repository already owns design authorities, memory, and browser checks. Declare those paths and checks explicitly.
5. Run governance apply, manifest validation, plane audit, architecture graph, and program status. Resolve owner decisions in canonical repository authorities, never in generated files.
6. Execute ready backlog waves through scoped task packets. Run only checks selected by repository rules and graph impact, then broaden to the repository's release gates.
7. Use `program complete` only after every declared item is terminal with required evidence or an authorized terminal disposition.

## Authority And Safety

- Repository authorities outrank package defaults.
- Untracked instructions and skills are visible but cannot govern future agents.
- Existing Atlas, backlog, component, token, Playwright, CI, and release systems are preserved.
- Exact source paths and generated maps are hash-bound so later governing drift fails closed.
- Architecture discovery is static and bounded; excluded dependency, artifact, and build trees are pruned before traversal.
- Design remains locked while vision, governance, architecture, security, ownership, or evidence conflicts are unresolved.
- Automatic design repair remains allowlisted and stops after three iterations or an authority, scope, or architecture boundary.
- Baselines and quality thresholds cannot be mutated to create a passing result.

## QuietPilot Pilot

The repository-native pilot binds QuietPilot's existing Enterprise Atlas, MVP golden path, architecture and domain invariants, UI/UX governance, design-system records, proof-boundary checks, and commercial-journey verification. The resulting program identifies the executable journey, all completion-governed items, and exact blockers without creating a parallel design or backlog system.

The pilot is intentionally blocked before design while QuietPilot still contains owner-governed conflicts, incomplete Atlas records, untracked V1 skills, and backlog items without explicit actor outcomes and success signals. That stop is successful enforcement, not a completion claim.
