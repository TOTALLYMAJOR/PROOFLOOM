# Claude Adapter

Use the install script to copy the skills into the Claude skills directory:

```bash
./scripts/install-claude-skills
```

Then use [CLAUDE.md](/home/administrator/design-intelligence/adapters/claude/CLAUDE.md) as a starting point only when the consuming repository does not already provide equivalent design instructions.

Adapter rules:

- Repository truth outranks adapter defaults.
- Use `design-language` first, not generic restyling.
- Run `design-intelligence assess` or `design-intelligence context` before broad UX changes.
- Treat `design-linter` and `visual-review` as evidence layers, not taste engines.
- Retrieve bounded memory and validate a design contract before material implementation.
- Do not update baselines, lower thresholds, or continue repairs beyond three iterations.
