<!-- design-intelligence: derived-view -->
# Design Decisions

This file is a navigation view, not a second ledger. Canonical records live in:

- `.design/memory/decisions.jsonl`
- `.design/memory/outcomes.jsonl`
- `.design/memory/exceptions.jsonl`
- `.design/memory/product-rules.json`

Lifecycle:

```text
proposal -> implementation -> validation -> outcome -> promotion
```

Accepted portfolio, archetype, and product rules require explicit human authority. Accepted surface and component decisions require a linked outcome and validation evidence. Revisions append a new record with the same durable ID and a higher revision number.
