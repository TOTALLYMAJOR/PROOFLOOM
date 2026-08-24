---
name: reference-intelligence
description: "Analyze external references, screenshots, and admired products to extract transferable principles without copying their identity."
---

# Reference Intelligence

Use this only when an external reference is genuinely useful.

Its job is:

> Learn from strong references without allowing them to outrank product truth.

## Rules

- Treat a supplied URL or `DESIGN.md` as `RESEARCH_REQUIRED`, not as analyzed evidence.
- Never say "make it look like X" and stop there.
- Decompose each reference into observed pattern, why it works, relevance here, and an original transformation.
- Existing repository behavior, governance, and tokens outrank the reference.
- Reject references that would erase intentional product differentiation.
- Record source, role, observed pattern, why it works, product relevance, original transformation, and rejected identity elements in the mission reference ledger.
- Emit `reference-analysis.schema.json` when the adoption CLI is available. Bind URL captures and verified capability claims to repository-relative SHA-256 evidence. Bind `ABSENT` claims to structured repository-search evidence; otherwise mark them `UNRESOLVED`.
- Treat any analyzer recommendation as advisory. `design-intelligence adopt` owns deterministic `ADOPT`, `ADAPT`, `DEFER`, `DECLINE`, and `BLOCKED` decisions.

## Output shape

- architectural reference
- interaction reference
- visual reference
- typography reference
- navigation reference
- mobile reference
- conversion reference

One reference does not need to solve every problem.

For sites, use the repository's `design:reference:capture` Playwright adapter when available. Captured bytes are evidence, not proof that a feature belongs in the product.

## Routing

- Read [references/reference-analysis.md](references/reference-analysis.md) for the decomposition method.
- Read [references/scoring-model.md](references/scoring-model.md) when multiple references compete.
- Read [references/originality.md](references/originality.md) before approving a design that feels too template-like.
