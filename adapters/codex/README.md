# Codex Adapter

Use the unified installer to expose the CLI and copy the Design Intelligence skills into the Codex skills directory:

```bash
./scripts/install
```

The older `./scripts/install-codex-skills` command refreshes only the skill files.

Then use [AGENTS.md](/home/administrator/design-intelligence/adapters/codex/AGENTS.md) as a starting point only when the consuming repository does not already have equivalent design instructions.

Adapter rules:

- Treat this as a routing layer, not a competing authority.
- Run `design-intelligence assess` before major design-system or workflow changes.
- Keep runtime structure unless repository evidence and migration scoring justify convergence.
- Retrieve bounded memory and validate a design contract before material implementation.
- Use the consuming repository's existing Playwright hierarchy when present; use the packaged route runner only when the repo lacks an equivalent.
- Never promote a baseline or apply a repair without explicit authority and evidence.
