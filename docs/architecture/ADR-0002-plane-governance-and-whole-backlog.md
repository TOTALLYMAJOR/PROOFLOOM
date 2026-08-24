# ADR-0002: Govern intent, architecture currency, intelligence, and the whole backlog as control-plane projections

- Status: Accepted
- Date: 2026-08-23
- Owners: repository maintainers

## Context

The Phase 0-3 facade could bind instructions, task context, affected checks, and existing design evidence. It could not prove what user outcome a task served, whether architecture guidance was current for repository context, how reasoning capability was selected, or whether a completion statement covered the whole backlog rather than the next items.

Copying canonical product documents, architecture trees, backlogs, or model-provider configuration into the package would create competing authorities and make consuming repositories less reliable.

## Decision

Add three projections under `spec.planes`:

- Intent uses a hash-bound index into canonical vision, principles, personas, requirements, journeys, metrics, constraints, and experiments.
- Architecture uses a dated repository profile against a bundled official-source standards catalog, with explicit applicability, disposition, evidence, and expiry.
- Intelligence uses repository instruction and skill discovery plus vendor-neutral capability classes selected by work type, risk, and required capabilities.

Add whole-backlog accounting under the Intent plane. Every declared completion-governed source is parsed and dependency-checked. Completion requires every item to be completed, cancelled with authority, or deferred with authority. Blocked and staged work remains visible.

Keep command execution plan-only. Keep product, architecture, security, production, and baseline decisions human-gated.

## Consequences

- User-facing tasks cannot pass without journey, requirement, and success-metric links.
- Stale source hashes, reviews, or standards versions fail closed.
- A consuming repository must review discovery and author its own plane bindings; initialization cannot invent product intent.
- Full-backlog accounting may expose more open work than short-horizon execution plans, but it prevents false completion claims.
- Vendor changes do not require task or governance schema changes.
- The package can report engineering alignment but cannot claim external certification or consuming-product acceptance.

## Rejected alternatives

- A central copied knowledge graph was rejected because it would compete with repository authorities.
- Model-provider names in task packets were rejected because they couple governance to vendors and hide capability requirements.
- Treating blocked or staged items as complete was rejected because it makes portfolio status untruthful.
- Automatically executing the entire backlog was rejected because dependencies, architecture, security, product, and release gates retain authority.
