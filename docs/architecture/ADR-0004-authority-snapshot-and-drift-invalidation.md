# ADR-0004: Authority Snapshot and Drift Invalidation

- Status: Accepted
- Date: 2026-09-17
- Owner: repository maintainers

## Context

Proofloom can inspect a clean worktree while another agent changes the canonical checkout. The QuoteFlow pilot exposed the consequence: feature-specific journey documents and a generic end-to-end test were treated as sufficient product-journey authority, while a canonical product-intelligence system was created concurrently outside the pilot snapshot. The isolated AgentFlow task remained reproducible for its commit, but the program reported a broader current-readiness conclusion that its evidence did not support.

Git commit binding alone is insufficient when relevant authority is modified or untracked. Filename keywords, isolated uses of words such as `canonical`, and unrelated E2E commands are also insufficient evidence of canonical authority or journey proof.

## Decision

Proofloom governance and AgentFlow handoff use fail-closed authority snapshots.

- A canonical authority must be explicitly declared. For Markdown and other text authorities, `Authority: canonical <roles>` declares the named roles. An existing repository-native canonical index may instead bind artifacts through a `Required artifacts`, `Canonical authorities`, or `Authority map` section. Repository instruction files and `.dev/intent-index.json` retain their established explicit bindings.
- Journey fragments remain candidates until one source explicitly declares canonical journey authority. Mentioning canonical facts, pricing, or another authority does not promote a journey document.
- Journey proof is linked only when the canonical journey source names an existing test path. A repository-level E2E command cannot stand in for that relationship.
- Untracked documents or configuration that match critical authority roles lock design. They must be adopted, removed, or explicitly excluded before convergence.
- Added, changed, and removed critical authorities all invalidate an applied convergence manifest. Additions are not treated as harmless drift.
- An approved AgentFlow handoff uses schema `2.0.0` and binds the Git HEAD, clean-worktree assertion, complete critical-authority source set, authority-state digest, governance-report digest, and aggregate snapshot digest.
- Approved handoffs remain non-executable until the repository-bound verifier recomputes every binding against the current checkout. Static schema validation alone never authorizes execution.
- Drift preserves prior evidence as historical evidence but changes the current result to invalid. It never rewrites the old receipt as if the old run had not occurred.

The program does not rely on a cooperative repository lock as its trust boundary. Locks may reduce collisions, but snapshot comparison and invalidation remain required because other tools and users may not honor a lock.

## Consequences

- Repositories with only inferred or fragmented product authority will return `REVIEW_REQUIRED` until an owner ratifies the canonical source.
- Mature repositories may need a small metadata addition to an existing authority; Proofloom does not create a parallel journey or product system.
- Dirty worktrees cannot produce execution-authorized AgentFlow handoffs. Work must be committed or captured in an explicitly reviewed clean overlay checkout.
- Handoff schema `1.0.0` remains historical evidence only. AgentFlow consumers must adopt schema `2.0.0` before a new end-to-end execution can be called current.
- More runs will stop on ambiguity. That is intentional: a visible stop is safer than a false green readiness claim.

## Rejected Alternatives

- Treating any filename containing `journey`, `workflow`, or `architecture` as canonical was rejected because feature fragments do not establish product authority.
- Treating any use of `canonical` or `authoritative` as a binding declaration was rejected because negative and cross-domain statements create false positives.
- Treating authority additions as warnings was rejected because a new canonical source can invalidate the entire model used by an in-flight run.
- Relying only on the Git commit was rejected because dirty and untracked authority can materially change the live repository without changing `HEAD`.
- Relying only on human review was rejected because exact snapshot comparison is deterministic and should be enforced before asking a person to judge the content.
