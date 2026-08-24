# ADR-0001: Add a control-plane facade, not a second intelligence system

- Status: Accepted
- Date: 2026-08-23

## Context

Design Intelligence already owns institutional design memory, contracts, reference adoption, Playwright evidence, quality scoring, governed baselines, bounded repair, and self-audit. A development control plane needs repository-wide task, context, and verification coordination, but duplicating those design authorities would create conflicting truth and slow development.

## Decision

Add a dependency-free `devctl` facade and a small `.dev` task store. The facade reads one repository manifest, retrieves bounded trust-ranked context, maps changed paths to declared checks, and delegates design and visual audits to existing Design Intelligence functions.

The manifest is JSON-compatible YAML so Python's standard library is sufficient. Commands are stored as argument arrays, not shell strings. Phase 0-3 returns plans only and cannot execute arbitrary task commands.

## Consequences

- Existing authorities remain canonical and reusable across repositories.
- Installation remains lightweight and does not require a service, database, or YAML package.
- Consumers must deliberately map their real instructions, architecture, backlog, tests, and design authorities.
- More advanced command execution, policy engines, graph storage, and multi-agent orchestration are deferred until evidence shows deterministic manifests and task packets are insufficient.
