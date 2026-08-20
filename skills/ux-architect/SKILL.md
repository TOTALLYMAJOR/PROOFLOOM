---
name: ux-architect
description: "Organize the user's task, decisions, and information hierarchy for substantial workflow, navigation, or product-structure changes."
---

# UX Architect

This skill owns:

> How should the user's task be organized?

Use it when the issue is workflow clarity, decision flow, information architecture, navigation, or progressive disclosure rather than pure styling.

## Decision model

For each important surface, identify:

- actor
- object
- goal
- decision
- state
- blocker
- authority
- next action

If these are unclear, the problem may not be visual.

## Required behavior

- Diagnose whether the failure is workflow, information hierarchy, IA, or interaction.
- Make one dominant action obvious.
- Keep secondary capability discoverable without competing for attention.
- Use product state to decide what should be visible now versus later.
- Preserve existing repository truth when it already captures the task model well.

## Routing

- Read [references/actor-task-model.md](references/actor-task-model.md) for the base model.
- Read [references/information-hierarchy.md](references/information-hierarchy.md) when hierarchy and action priority are unclear.
- Read [references/progressive-disclosure.md](references/progressive-disclosure.md) when complexity is real but should not be visible all at once.
- Read [references/workflow-diagnosis.md](references/workflow-diagnosis.md) when the team is mistaking workflow defects for visual polish.

## Coordination

- Use `design-language` when the task model is clear and visual expression is next.
- Use `visual-review` after implementation to confirm hierarchy actually renders the intended outcome.
