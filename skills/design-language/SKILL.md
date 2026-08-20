---
name: design-language
description: "Determine or preserve a product's visual and interaction language for frontend, UX, responsive, and design-system changes. Use after repo-fit when the task materially changes interface behavior or presentation."
---

# Design Language

Use this as the primary Design Intelligence skill.

Its job is:

> Determine and protect the visual and interaction language appropriate to this product.

## Core rule

Before modifying an existing interface:

> Understand the current design language before inventing a new one.

Do not solve structural UX defects with cosmetic changes.

## Authority order

1. Explicit current user instruction
2. Existing product behavior and requirements
3. Existing repository governance
4. Existing architecture or design documentation
5. Existing tokens and component primitives
6. Existing implementation patterns
7. User-supplied screenshots or references
8. Approved external references
9. General design convention
10. Agent aesthetic preference

## Required behavior

- Run `repo_fit` before substantial redesign, design-system work, or repository-wide UI changes.
- Preserve current runtime structure unless a higher-authority instruction explicitly calls for migration.
- Distinguish visual defects from hierarchy, information architecture, interaction, workflow, responsive, accessibility, component-system, or drift problems.
- Treat product specificity as mandatory. Reject generic SaaS restyling that could fit dozens of unrelated products.

## What this skill owns

- product personality
- information density
- typography
- color roles
- geometry
- surface hierarchy
- interaction language
- motion
- responsive behavior
- accessibility expectations
- product-specific visual identity

## Working model

1. Discover current evidence.
2. Diagnose the actual defect type.
3. Decide the smallest coherent intervention.
4. Reuse existing tokens and primitives wherever reasonable.
5. Hand off to `visual-review` when rendered output exists.

## Routing

- Read [references/design-principles.md](references/design-principles.md) for the general reasoning model.
- Read [references/surface-hierarchy.md](references/surface-hierarchy.md) when structure, panel nesting, or page composition is the issue.
- Read [references/interaction-language.md](references/interaction-language.md) when control states, motion, or feedback are involved.
- Read [references/responsive-design.md](references/responsive-design.md) when desktop and mobile should differ in priority, not merely size.
- Read [references/accessibility.md](references/accessibility.md) when accessibility changes the design decision.
- Read [references/product-archetypes.md](references/product-archetypes.md) when product purpose should change the solution.
- Read [references/anti-patterns.md](references/anti-patterns.md) before approving a visually dramatic but weakly reasoned redesign.

## Coordination with other skills

- Use `ux-architect` when the problem is task or information organization.
- Use `reference-intelligence` only when an external reference is genuinely useful.
- Use `visual-review` after implementation or when a screenshot or render is available.
