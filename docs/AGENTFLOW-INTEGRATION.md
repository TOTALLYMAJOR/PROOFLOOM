# AgentFlow integration contract

Design Intelligence and AgentFlow integrate through two versioned, hash-bound documents. They do not share a database or transfer authority implicitly.

1. Design Intelligence produces a `design-intelligence/governed-task-handoff`.
2. A repository owner reviews and approves the handoff.
3. AgentFlow verifies the exact handoff and source commit before planning.
4. AgentFlow binds the handoff digest to its immutable plan and execution evidence.
5. AgentFlow emits an `agentflow/build-receipt` after execution.
6. Design Intelligence audits the receipt against the exact handoff and records the outcome separately.

A handoff in `PROPOSED` state cannot authorize execution. A passing build receipt proves only the stated local execution and integration boundary. It does not prove deployment, provider behavior, production readiness, customer acceptance, or business outcomes.

Canonical schemas:

- `design_intelligence/data/schemas/governed-task-handoff.schema.json`
- `design_intelligence/data/schemas/agentflow-build-receipt.schema.json`
