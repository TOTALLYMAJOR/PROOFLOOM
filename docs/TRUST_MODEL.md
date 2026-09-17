# Proofloom Trust and Assurance Model

Proofloom is trustworthy only when its conclusions are reproducible from the same declared authority snapshot. It does not ask operators to trust an AI interpretation, a green label, or a hash in isolation.

## Trust invariants

1. **Explicit authority:** candidate evidence cannot silently become canonical authority.
2. **Complete source selection:** tracked, modified, and relevant untracked authority are visible before convergence.
3. **Exact journey proof:** a canonical journey names its proof; a generic E2E suite is supporting evidence only.
4. **Fail-closed drift:** adding, changing, or removing critical authority invalidates the current conclusion.
5. **Clean execution snapshot:** an approved AgentFlow handoff binds a clean Git checkout and the complete critical-authority set.
6. **Independent recomputation:** execution authorization requires repository-bound verification at the transition, not only validation performed when the document was created.
7. **Historical honesty:** an invalidated run remains preserved as evidence for its old snapshot but cannot be presented as current.

## Authority declaration

Proofloom may discover candidate authorities from repository structure and filenames. Readiness requires an explicit binding. A repository-owned text authority declares a role with:

```text
Authority: canonical journeys
```

Multiple applicable roles may be comma-separated. The declaration binds the existing document; it does not authorize Proofloom to rewrite product truth. `AGENTS.md`, `CLAUDE.md`, and `.dev/intent-index.json` retain their established special bindings.

An existing repository-native model is equally valid when a document explicitly identifies itself as the canonical entry point or index and binds repository-relative artifacts under `Required artifacts`, `Canonical authorities`, or `Authority map`. Proofloom hashes both the index and each linked authority. This is how QuotePilot's product-intelligence index binds its journey, capability, metric, signal, target, guardrail, and experiment artifacts without adding Proofloom-specific metadata to those files.

## Run states

| State | Meaning |
|---|---|
| `DISCOVERED` | Candidate evidence was found; canonicality is not established. |
| `REVIEW_REQUIRED` | Authority is missing, ambiguous, untracked, conflicting, stale, or insufficiently proven. |
| `CONVERGED` | Required authorities were explicitly bound against one recorded state. |
| `EXECUTION_READY` | The approved handoff was independently recomputed against a clean matching checkout. |
| `EXECUTED` | AgentFlow completed against the bound handoff and commit. |
| `CURRENT` | Final verification still matches the canonical checkout. |
| `INVALIDATED` | Later evidence or drift prevents the prior conclusion from being current. |

Only repository-bound verification may produce execution authorization. Static handoff validation can show that a document is well-formed, but its result is not `EXECUTION_READY`.

## Snapshot certificate

Governed handoff schema `2.0.0` binds:

- exact Git `baseCommit`;
- declared `worktreeState: clean`;
- complete critical-authority paths and SHA-256 values;
- aggregate critical-authority state digest;
- governance-report digest;
- aggregate governed-snapshot digest.

The verifier recomputes these fields and also reruns governance convergence. A dirty worktree, untracked critical authority, different `HEAD`, source mismatch, governance mismatch, or snapshot mismatch makes execution authorization false.

## QuoteFlow incident regression

The regression suite reproduces the failure that motivated this contract:

1. feature journeys exist without canonical product-journey authority;
2. an unrelated E2E command exists;
3. Proofloom must keep design locked with `MISSING-CANONICAL-JOURNEY`;
4. a new untracked product-intelligence journey appears;
5. Proofloom must report untracked critical authority and refuse readiness;
6. a newly tracked critical authority after convergence must produce `DRIFT_DETECTED`;
7. an approved handoff without current repository proof must keep `executionAuthorized: false`.

## Evidence boundary

These controls establish deterministic source and local-execution integrity. They do not establish deployment, hosted behavior, provider outcomes, customer acceptance, business outcomes, or independent security certification.

The Design Intelligence side now emits and verifies the `2.0.0` contract. AgentFlow must adopt and enforce the same repository-bound fields before the next cross-repository pilot can claim end-to-end current execution.
