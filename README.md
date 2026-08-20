# Design Intelligence v0.1.1

Design Intelligence is a small, production-usable repository that gives Codex and Claude a reusable product-design capability without turning into a second application scaffold.

The governing objective is:

> Product intent -> repository evidence -> design reasoning -> implementation constraints -> rendered validation -> design learning.

## What v0.1 includes

- `skills/design-language`: the primary visual and interaction language skill
- `skills/ux-architect`: task, information, and workflow organization guidance
- `skills/reference-intelligence`: external reference analysis without copying
- `skills/visual-review`: rendered output review and defect classification
- `repo_fit/`: a deterministic, read-only repository inspector and assessor
- `templates/`: reusable design profile, contract, decision, and review templates
- `examples/product-profiles/`: QuotePilot, QuietPilot, and LeaguePilot examples
- `adapters/codex` and `adapters/claude`: thin integration guidance
- `tests/fixtures/`: bounded repositories used to prove repo-fit behavior

## What v0.1 does not include

- database
- dashboard
- Docker
- knowledge graph
- autonomous repair
- generalized repo migration platform
- second component system
- second token system
- parallel E2E hierarchy
- automatic restructuring

## Authority order

Existing repository truth always outranks package defaults.

1. Explicit current user instruction
2. Existing product behavior and requirements
3. Existing repository governance
4. Existing architecture or design documentation
5. Existing tokens and component primitives
6. Existing implementation patterns
7. User-supplied references
8. Approved external references
9. General convention
10. Agent aesthetic preference

## Repo-fit

Run repo-fit before substantial design work:

```bash
./scripts/inspect-repo /path/to/repository
```

This stays read-only and answers:

- what already exists here?
- what should be preserved?
- should design intelligence `KEEP`, `ALIGN`, `CONVERGE`, or `RESTRUCTURE` around the current scaffold?
- can knowledge alignment solve the problem without runtime migration?

## Install

Codex:

```bash
./scripts/install-codex-skills
```

Claude:

```bash
./scripts/install-claude-skills
```

Both scripts accept an optional destination path.

## Validation

Run the repo-fit tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Validate the skill structure:

```bash
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/design-language
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/ux-architect
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/reference-intelligence
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/visual-review
```

## Release

`VERSION` and package metadata are pinned to `0.1.1`. Tag releases after validation passes.
