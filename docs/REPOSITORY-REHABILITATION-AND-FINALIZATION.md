# Repository Rehabilitation And Product Finalization

## Purpose

Design Intelligence now treats mature repositories differently from greenfield design work.

A repository can contain substantial code, tests, documents, skills, and release automation while still being unable to finish the product. The common failure is not lack of implementation volume. It is loss of shared product understanding:

- vision changed without explicit ratification;
- user journeys exist but are not connected to code and end-to-end proof;
- active, staged, historical, and generated documents are treated as equal authority;
- agent instructions, skills, hooks, ADRs, and backlog rules disagree;
- a declared command points to evidence that no longer exists;
- backlog items optimize local features without completing the governing journey;
- design work begins before product, architecture, and authority conflicts are resolved.

The rehabilitation system restores this sequence:

```text
repository identity
  -> tracked governing evidence
  -> vision, actors, requirements, journeys, architecture, and backlog
  -> authority lifecycle and conflict treatment
  -> bounded convergence actions
  -> owner ratification where required
  -> finalization plan and executable journey proof
  -> design adoption
  -> rendered verification and institutional learning
```

## Status Model

- `UNDERSTANDING_INCOMPLETE`: the repository cannot explain one or more core product authorities.
- `GOVERNANCE_CONFLICTED`: the model is visible, but blocking conflicts, damage, drift, or unratified authority remain.
- `EXECUTION_READY`: product understanding is coherent enough to execute the remaining non-design convergence work.
- `DESIGN_READY`: vision, journey, authority, architecture, backlog, and proof are coherent enough to enter the existing Design Intelligence workflow.

`DESIGN_READY` is not a completion, merge, release, deployment, or customer-outcome claim.

## Commands

Start with the human-readable audit:

```bash
design-intelligence govern audit --root /path/to/repository
```

Build the action plan:

```bash
design-intelligence govern plan --root /path/to/repository
```

Apply only derived bindings and drift protection:

```bash
design-intelligence govern apply --root /path/to/repository
```

Verify convergence before design:

```bash
design-intelligence govern verify --root /path/to/repository
```

The same lifecycle is available through `devctl govern`.

## What Audit Covers

The scanner uses tracked repository files when Git is available. Untracked instructions and skills are reported but never promoted to authority. Generated artifacts, exports, build output, dependency trees, and nested output worktrees are excluded.

The map covers:

- root and scoped `AGENTS.md`, `CLAUDE.md`, custom instructions, and hooks;
- specialist skills and duplicate scoped definitions;
- vision, strategy, principles, actors, personas, requirements, success metrics, and experiments;
- binding journeys, routes, implementation links, and executable proof;
- architecture documents, accepted ADRs, contracts, schemas, boundaries, and security controls;
- canonical, staged, and historical backlog sources;
- design systems, component registers, token authorities, accessibility, and visual validation;
- delivery, release, rollback, provider, evidence, incident, and audit controls;
- package commands that reference missing test, verification, or release files;
- existing equivalent systems such as an Enterprise Atlas or repository-native control plane.

Multiple documents are not automatically a conflict. Scoped and complementary authorities are preserved. Historical, superseded, generated, evidence-only, and untracked material cannot silently become current policy.

## What Apply Changes

`govern apply` writes only generated files under `.dev/governance/`:

- `governance-map.json`: authority, lifecycle, journey, backlog, conflict, and damage map;
- `repository-adapter.json`: bindings from the repository's existing model into Design Intelligence;
- `convergence-manifest.json`: hashes of critical governing sources for later drift detection;
- `rehabilitation-plan.json`: automatic and authority-bound completion work;
- `HUMAN-READOUT.md`: product-language explanation of the current repository;
- `OWNER-RATIFICATION.md`: pending decisions that require repository authority.

These files are derived navigation and execution aids. They do not replace product intent, ADRs, security policy, the canonical backlog, or the design system. The command refuses to overwrite a file that it did not generate.

## Automatic Versus Human Action

The tool may automatically:

- bind an existing equivalent governing model;
- create derived indexes and adapters;
- detect broken command targets and untracked governing files;
- inventory the full declared backlog and map supported items to journey stages;
- baseline critical authority hashes and detect later drift;
- produce an ordered rehabilitation plan and owner-decision packet;
- block design when critical prerequisites are unresolved.

The tool may not silently:

- redefine or approve product vision;
- decide between conflicting canonical authorities;
- accept an ADR, security exception, production risk, or ownership transfer;
- mark backlog work completed without its required evidence;
- merge, deploy, release, mutate providers, or promote visual baselines;
- rewrite runtime architecture merely to resemble the package defaults.

Those decisions remain in the repository's existing authority process. After ratification, the affected canonical source is updated there, `govern apply` is rerun, and `govern verify` establishes the new reviewed baseline.

If a convergence manifest already exists and a critical authority changed, ordinary apply fails closed. The repository owner must provide a receipt with `kind: AuthorityDriftRatification`, `decision: ACCEPT_AUTHORITY_DRIFT`, `authority: repository-owner`, the exact changed or missing paths, and the current `authorityStateSha256` reported by the audit:

```bash
design-intelligence govern apply --root /path/to/repository --ratification /path/to/owner-receipt.json
```

The receipt records the owner, timestamp, reason, exact scope, and authority-state digest. A stale or overbroad receipt is rejected.

## Mature Repository Enforcement

Repositories with an existing equivalent system, such as an Atlas or development control plane, are fail-closed immediately because their own governing model must be honored. Repositories without an equivalent begin in advisory mode until `govern apply` establishes a convergence manifest. This preserves early experimentation while making rehabilitation explicit for mature products.

Once a convergence manifest exists, any missing or changed critical instruction, vision, journey, architecture, backlog, security, or design authority fails verification. A later agent cannot silently alter the product model and continue into design.

Removing the manifest does not return an applied repository to advisory mode. If any applied governance artifacts remain while the manifest is missing, the design gate stays locked until the generated baseline is restored and verified.

## Design Boundary

Design begins only after governance convergence. The existing sequence then applies:

```text
govern verify
  -> design-language
  -> ux-architect
  -> reference-intelligence when useful
  -> design contract
  -> implementation
  -> Playwright, accessibility, DOM/state, quality, and drift evidence
  -> bounded repair
  -> institutional memory
```

External references remain evidence, never product authority. Features are adopted, adapted, deferred, declined, or blocked against the recovered vision, journey, architecture, backlog, design system, and proof boundaries.
