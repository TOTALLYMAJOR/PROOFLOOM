# Design Intelligence Adapter

- Existing repository authorities outrank Design Intelligence defaults.
- When `devctl.yaml` exists, use `devctl task context` and `devctl verify affected` to select bounded evidence and repository checks; do not treat the manifest as a replacement authority.
- Start material design work with `design-intelligence "<plain-English task>"` from the consuming repository.
- Do not implement a recommended direction until the user explicitly selects it.
- Run `design-intelligence assess` before major interface, workflow, or design-system changes.
- Use `design-language` as the primary skill.
- Use `ux-architect` when the problem is task organization, hierarchy, or progressive disclosure.
- Use `reference-intelligence` to transform references, never to clone them.
- Use `design-linter` for deterministic drift checks and `visual-review` after implementation.
- Prefer knowledge alignment over runtime migration.
- Use `devctl design` and `devctl visual` only as thin adapters to the existing Design Intelligence and Playwright authorities.
