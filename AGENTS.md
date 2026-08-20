# Design Intelligence Repository Guide

Use this repository to maintain the reusable package itself, not to redefine consuming repositories.

## Operating rules

- Existing repository authorities outrank package defaults.
- `repo_fit` is read-only and bounded. Do not turn it into a generalized migration platform.
- Prefer knowledge alignment over runtime migration when that captures most of the value.
- Do not add databases, dashboards, Docker, autonomous repair, or a competing component system.

## Map

- `skills/`: the reusable Codex and Claude skill content
- `repo_fit/`: bounded repository discovery and assessment
- `templates/`: reusable writing artifacts for product design work
- `examples/product-profiles/`: QuotePilot, QuietPilot, and LeaguePilot examples
- `adapters/`: thin integration guidance for Codex and Claude
- `tests/fixtures/`: small sample repositories that prove repo-fit behavior

## Validation

- Run `python3 -m unittest discover -s tests -p 'test_*.py'`.
- Run the skill validator for each skill before release changes.

## Release discipline

- Keep `VERSION` and `pyproject.toml` aligned.
- Tag only after validation passes.
