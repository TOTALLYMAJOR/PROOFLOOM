# Traffic Control receipt audit

Proofloom audits an AgentFlow `agentflow/build-receipt@1.0.0` against the exact
approved `design-intelligence/governed-task-handoff@2.0.0` that authorized the
run. The audit rejects substituted handoffs, missing or additional tasks,
unintegrated work, absent result or integration commits, changes outside task
ownership, failed or skipped governed validation commands, missing required
evidence, altered Governor records, broken decision chains, authority drift,
and completion without a final `CONTINUE` decision.

The passed claim is intentionally narrow: **AgentFlow local execution and
integration evidence verified.** Deployment, production, provider delivery,
customer access, human acceptance, and product outcomes require their own
evidence and are never inferred from this receipt.

Use `audit_traffic_control_receipt(receipt, handoff)` from
`design_intelligence.traffic_control_audit`. The function is read-only and
returns a `PASS` or `FAIL` result with explicit errors, completion state,
Governor verification state, proof boundary, and bounded claim.
