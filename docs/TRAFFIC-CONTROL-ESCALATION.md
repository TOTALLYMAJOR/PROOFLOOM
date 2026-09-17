# Traffic Control structural escalation

A Governor `REQUEST_RECONSIDER` or `PROPOSE_REPLAN` decision is a durable
proposal, never execution authority. Proofloom binds the triggering decision,
the original approved handoff, the run, and at least two comparable
alternatives into a read-only `REVIEW_REQUIRED` proposal.

Only human or repository authority may record approval, rejection, a revision
request, or cancellation. Approval selects one existing alternative and must
include a new independently approved governed handoff. The resolution records
the prior and replacement handoff identities and digests; it never mutates the
old handoff or decision history. Non-approved resolutions remain
non-executable. Resolution records are append-oriented and hash-linked through
`previousRecordHash`.
