---
name: visual-review
description: "Review rendered UI, screenshots, or implemented surfaces to classify defects, validate responsive behavior, and decide whether the design intent survived implementation."
---

# Visual Review

This skill answers:

> Did we actually implement the design well?

Use it when rendered output, screenshots, or a working surface exists.

## Review rules

- Validate the rendered result, not only the source code.
- Prefer existing repository browser tooling, screenshot harnesses, or validation outputs when available.
- Classify defects by root cause: visual, hierarchy, IA, interaction, workflow, responsive, accessibility, component, or drift.
- Review desktop and mobile intentionally.
- Prefer evidence and severity over taste-based commentary.
- Do not turn this into an autonomous repair loop. The skill reviews; implementation is separate.

## Routing

- Read [references/review-rubric.md](references/review-rubric.md) for the scoring categories.
- Read [references/responsive-review.md](references/responsive-review.md) when layout changes across breakpoints.
- Read [references/visual-defects.md](references/visual-defects.md) when classifying issues precisely.

## Output

- verdict
- severity
- root cause
- evidence
- preserve / change guidance
- remaining debt
