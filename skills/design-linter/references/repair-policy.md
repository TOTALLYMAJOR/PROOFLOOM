# Repair Policy

Bounded repair is optional and conservative.

Rules:

- max 3 iterations
- deterministic P0/P1 and clear P2 only
- never weaken tests, thresholds, or baselines
- never hide functionality to pass validation
- escalate to human judgment when semantics are ambiguous
