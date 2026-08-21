# Design Intelligence Repository Guide

This repository owns the reusable utility itself. It does not outrank consuming repositories.

## Operating rules

- Design intelligence is the primary mission; repository intelligence is supporting infrastructure.
- Existing repository authorities outrank package defaults.
- Read-only by default. Only write artifacts when an explicit output path or installation target is requested.
- Prefer knowledge alignment over runtime migration when it captures most of the value.
- Do not add a second component system, second token system, second backlog, or second E2E hierarchy.

## Map

- `design_intelligence/`: vendor-neutral core package and CLI
- `repo_fit/`: V0.1 compatibility wrappers
- `skills/`: concise skills plus reference docs
- `templates/` and `examples/`: reusable design artifacts and product profiles
- `adapters/`: thin Codex and Claude adapter guidance
- `docs/`: architecture and release notes
- `tests/fixtures/`: bounded proof repositories and manifests

## Validation

- Run `python3 -m unittest discover -s tests -p 'test_*.py'`.
- Run the skill validator for each skill before tagging.
- Keep `VERSION`, `pyproject.toml`, and `design_intelligence/__init__.py` aligned.
