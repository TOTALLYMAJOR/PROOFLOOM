# Reference Analysis

Decompose each reference into:

- observed pattern
- why it works
- where it is relevant here
- how it must be transformed
- what must not be imported

Never stop at "make it look like X."

When the Design Adoption Gate is available, write observations to the packaged `reference-analysis.schema.json`. Include empty arrays explicitly for keywords, required capabilities, protected risks, and identity elements. A model may supply `recommendedDecision`, but the deterministic gate ignores it. Never declare a capability `ABSENT` from model confidence alone: provide `evidenceMethod: repository-search` plus a hash-bound structured search receipt, or use `UNRESOLVED`.
