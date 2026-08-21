# Design Intelligence Architecture

## Core shape

`design_intelligence/` is the vendor-neutral core package.

It owns:

- bounded repository discovery
- scaffold reconciliation
- migration-risk scoring
- context generation
- reference transformation
- deterministic design linting
- visual-review aggregation
- validation and evidence packs
- conservative doctor / repair planning

`repo_fit/` remains as a compatibility layer for V0.1 entry points.

## Authority model

Design Intelligence does not become the new repository authority by default.

Priority order:

1. current user requirement
2. existing repository governance
3. existing architecture and design authorities
4. existing tokens, components, and implementation patterns
5. Design Intelligence guidance

## Read-only default

Every CLI command is read-only unless the user explicitly requests an output path or installation target.

Examples:

- `validate --evidence-pack-out ...` writes an evidence artifact
- install scripts copy skills into Codex or Claude skill directories

The utility does not silently mutate consuming repositories.

## Migration boundaries

Two migrations are scored separately:

- knowledge migration: docs, decisions, indexes, AGENTS navigation
- runtime migration: components, imports, package boundaries, filesystem structure

The default preference is 80/20 alignment:

- keep runtime structure
- converge duplicate authorities
- add only missing design capability

## Product archetypes

QuotePilot, QuietPilot, and LeaguePilot are data-backed product profiles.

They live outside the reasoning code as package data and human-readable examples so the core remains vendor-neutral.

## Evidence model

Material design work can produce an evidence pack containing:

- contract
- repo context
- before and after screenshots
- lint and accessibility findings
- visual-review findings
- decision summary
- remaining debt

This is a Git-friendly record, not a second dashboard or backlog.
