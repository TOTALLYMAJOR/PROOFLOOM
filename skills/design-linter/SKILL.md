---
name: design-linter
description: "Run deterministic checks for token, component, layout, responsive, and accessibility drift before or after material UI work."
---

# Design Linter

Use this skill when a deterministic check can catch design drift faster than model judgment alone.

Its job is:

> Surface clear, bounded violations without pretending every design problem is lintable.

## What this skill checks

- hard-coded colors and arbitrary values that bypass tokens
- duplicate primitives across competing component directories
- unsafe fixed widths and obvious off-screen positioning
- missing alt attributes
- icon-only buttons without accessible names

## Rules

- Treat a locked governance or journey gate as non-repairable by design lint. Do not propose cosmetic changes as a substitute for product convergence.
- Stay deterministic.
- Flag drift; do not invent aesthetic rules that the repository never adopted.
- Allow intentional exceptions when they are explicitly marked.
- Hand non-deterministic hierarchy or workflow problems back to `ux-architect` or `visual-review`.

## Routing

- Read [references/deterministic-rules.md](references/deterministic-rules.md) for the current lint boundaries.
- Read [references/drift-types.md](references/drift-types.md) when deciding whether a finding is token, component, layout, or accessibility drift.
- Read [references/repair-policy.md](references/repair-policy.md) before proposing bounded auto-repair.
