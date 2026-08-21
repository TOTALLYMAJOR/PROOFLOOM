<!-- design-intelligence: derived-view -->
# Design Debt

Canonical debt records live in `.design/memory/debt.jsonl` with owner, scope, status, creation date, and review date.

Use:

```bash
design-intelligence memory stale --root .
design-intelligence memory context --root . --product design-intelligence --surface "Design QA Control Deck fixture"
```

Current explicit debt: automated accessibility and DOM checks do not replace manual semantic review on a consuming production surface.
