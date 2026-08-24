# Control Plane Architecture Graph

## Purpose

The architecture graph answers: "If this task changes these files, what downstream code, contracts, journeys, tests, owners, and protected boundaries require attention?"

It augments the existing repository authorities and verification rules. It does not create a second architecture source of truth.

## Commands

Build the complete bounded static graph:

```bash
./scripts/devctl architecture graph \
  --root . \
  --format json \
  --output artifacts/control-plane/architecture-graph/graph.json
```

Trace a task and one or more changed paths:

```bash
./scripts/devctl architecture impact TASK-ARCHITECTURE-IMPACT-GRAPH \
  --changed design_intelligence/architecture_graph.py \
  --root . \
  --format json \
  --output artifacts/control-plane/architecture-graph/task-impact.json
```

`devctl impact` and `devctl verify affected` also include the architecture result. Graph-derived protected checks are added to the affected-verification plan, but commands are not executed automatically.

Quick CI uses `architecture graph --summary`. It performs the same bounded scan but emits only counts, limits, status, and `graphSha256`; use the full command with `--output` when node-and-edge evidence is required.

## Applying It To Another Repository

1. Run `devctl init --dry-run --root /path/to/repository` and review the discovered authorities, backlog, scripts, and proposed manifest without writes.
2. Run `devctl init` only after confirming the target is authoritative. Existing instructions, design systems, backlogs, tests, and CI remain in place.
3. Review `spec.planes.architecture.impactGraph`. Narrow `include`, preserve secret and generated-file exclusions, and set budgets appropriate to the repository.
4. Bind real ownership through CODEOWNERS or `ownershipRules`. Do not invent named owners when the repository has not declared them.
5. Declare protected `securityRules` with the existing verification command IDs and actual approval authority.
6. Bind active intent-index journeys to implementation paths with `journeyBindings`; journey test files remain sourced from the intent index.
7. Run `architecture graph`, inspect unresolved or truncated evidence, then use `architecture impact` on a bounded task before implementation.
8. Keep the graph command in quick CI. Keep execution, architecture approval, release, deployment, and baseline mutation in their existing governed paths.

## Output Interpretation

- `graphSha256` identifies the exact deterministic graph payload.
- Every edge includes repository evidence and an optional line number.
- `impactedPaths` is the downstream static blast radius, not proof that every runtime path executes.
- `securityBoundaries` and `requiredChecks` indicate protected review and verification obligations.
- `authorityRequired` means automation must stop at the declared boundary.
- `truncated: true` always produces `FAIL`; thresholds must be raised through review or the scan scope must be narrowed honestly.

## Known Limits

The engine intentionally does not execute code. Dynamic imports, framework aliases, generated clients, reflection, runtime dependency injection, non-literal URLs, database access hidden behind generic adapters, and external service topology may require explicit repository bindings or runtime evidence. Regular expressions identify common JavaScript and HTTP forms; they are not a full compiler.
