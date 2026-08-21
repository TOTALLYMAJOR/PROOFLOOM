# Codex Adapter

Use the install script to copy the Design Intelligence skills into the Codex skills directory:

```bash
./scripts/install-codex-skills
```

Then use [AGENTS.md](/home/administrator/design-intelligence/adapters/codex/AGENTS.md) as a starting point only when the consuming repository does not already have equivalent design instructions.

Adapter rules:

- Treat this as a routing layer, not a competing authority.
- Run `design-intelligence assess` before major design-system or workflow changes.
- Keep runtime structure unless repository evidence and migration scoring justify convergence.
