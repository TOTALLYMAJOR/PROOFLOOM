# AgentFlow integration contract

Design Intelligence and AgentFlow integrate through two versioned, hash-bound documents. They do not share a database or transfer authority implicitly. The governing trust decision is recorded in `docs/architecture/ADR-0004-authority-snapshot-and-drift-invalidation.md`.

1. Design Intelligence produces a `design-intelligence/governed-task-handoff`.
2. A repository owner reviews and approves the handoff.
3. AgentFlow verifies the exact handoff, clean worktree, complete critical-authority set, governance report, and source commit before planning.
4. AgentFlow binds the handoff digest to its immutable plan and execution evidence.
5. AgentFlow emits an `agentflow/build-receipt` after execution.
6. Design Intelligence audits the receipt against the exact handoff and records the outcome separately.

A handoff in `PROPOSED` state cannot authorize execution. An `APPROVED` handoff also remains non-executable until repository-bound verification passes. Static JSON validation is not execution authorization. A passing build receipt proves only the stated local execution and integration boundary. It does not prove deployment, provider behavior, production readiness, customer acceptance, or business outcomes.

Governed handoff schema `2.0.0` requires `baseCommit`, `worktreeState: clean`, `snapshotSha256`, the complete critical-authority sources, `stateSha256`, and `governanceReportSha256`. Create and verify an approved handoff with the exact repository root:

```bash
design-intelligence agentflow handoff-create --input handoff-source.json --output handoff.json --repository /absolute/repository/root
design-intelligence agentflow handoff-validate --input handoff.json --repository /absolute/repository/root
```

Without `--repository`, an approved handoff may be serialized for review but returns `REVIEW_REQUIRED`, `currencyVerified: false`, and `executionAuthorized: false`.

Canonical schemas:

- `design_intelligence/data/schemas/governed-task-handoff.schema.json`
- `design_intelligence/data/schemas/agentflow-build-receipt.schema.json`

Schema `1.0.0` handoffs remain historical evidence and are not current execution contracts.
