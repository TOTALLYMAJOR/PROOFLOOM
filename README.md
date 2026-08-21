# Design Intelligence v1.0.0

Design Intelligence is a production-grade, vendor-neutral utility for repository-aware design work. Its core mission is design intelligence: understand product intent, preserve existing design truth, reason about UX and design-system change, validate rendered outcomes, and record evidence without turning into a second application scaffold.

The governing objective is:

> Product intent -> repository evidence -> design reasoning -> implementation constraints -> rendered validation -> design learning.

## What 1.0.0 includes

- `design-intelligence inspect`: bounded repository discovery and capability mapping
- `design-intelligence assess`: scaffold reconciliation and preserve/integrate/add/migrate guidance
- `design-intelligence context`: UX and product context reasoning with QuotePilot, QuietPilot, and LeaguePilot profiles
- `design-intelligence review`: structured visual QA aggregation from existing browser or screenshot evidence
- `design-intelligence lint`: deterministic design drift, component, layout, and accessibility checks
- `design-intelligence refactor-risk`: knowledge-vs-runtime migration scoring and blast-radius analysis
- `design-intelligence validate`: combined repo-fit, lint, optional review, and evidence-pack output
- `design-intelligence doctor`: conservative repair planning and blockers summary
- `skills/`: concise Codex/Claude skills with progressive-disclosure references
- `adapters/codex` and `adapters/claude`: thin adapter guidance, not a competing governance layer
- `templates/` and `examples/product-profiles/`: reusable design artifacts and archetype examples

## Non-goals

- SaaS server
- mandatory cloud database
- Docker requirement
- vector DB or knowledge graph as canonical source
- second component library
- second token system
- second backlog
- second E2E hierarchy
- broad autonomous restructuring

## Authority order

Repository truth outranks package defaults.

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

## CLI

Install locally:

```bash
python3 -m pip install -e .
```

Core commands:

```bash
design-intelligence inspect --root /path/to/repo
design-intelligence assess --root /path/to/repo
design-intelligence context --root /path/to/repo --profile quotepilot
design-intelligence lint --root /path/to/repo
design-intelligence refactor-risk --root /path/to/repo
design-intelligence review --input work/review-manifest.json
design-intelligence validate --root /path/to/repo --review-input work/review-manifest.json --evidence-pack-out work/evidence-pack.md
design-intelligence doctor --root /path/to/repo
```

Legacy compatibility entry points still exist:

```bash
design-intelligence-inspect --root /path/to/repo
design-intelligence-assess --root /path/to/repo
```

## Skill installation

Codex:

```bash
./scripts/install-codex-skills
```

Claude:

```bash
./scripts/install-claude-skills
```

Both scripts accept an optional destination path.

## Architecture

See [docs/ARCHITECTURE.md](/home/administrator/design-intelligence/docs/ARCHITECTURE.md).

Key design decisions:

- `design_intelligence/` is the vendor-neutral core package.
- `repo_fit/` remains as a compatibility wrapper for the older V0.1 entry points.
- Product archetypes are data-backed profiles, not hard-coded logic branches spread across the codebase.
- Read-only by default. Evidence output only writes when an explicit output path is supplied.

## Validation

Run the full test suite:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Validate the skills:

```bash
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/design-language
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/ux-architect
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/reference-intelligence
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/visual-review
python3 /mnt/c/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/design-linter
```

## Release

`VERSION`, `pyproject.toml`, and package exports are aligned at `1.0.0`. Release notes live under [docs/](/home/administrator/design-intelligence/docs).
