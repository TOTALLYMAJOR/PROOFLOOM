# ADR-0003: Bounded Architecture Impact Graph

- Status: Accepted
- Date: 2026-08-23
- Owner: repository maintainers

## Context

Path-to-check rules are fast and deterministic, but they cannot explain which downstream modules, API consumers, schema users, journey tests, owners, or protected boundaries may be affected by a change. A repository-wide graph database or runtime tracer would duplicate authority, increase setup cost, and create confidence that static evidence cannot justify.

## Decision

Add a dependency-free static graph to the existing `devctl` facade. The graph reads only repository-relative files selected by `spec.planes.architecture.impactGraph` and emits typed nodes and source-evidenced edges.

The graph covers:

- source files and tests;
- Python and JavaScript/TypeScript imports;
- repository and imported packages;
- Next.js, FastAPI-style, and Express-style HTTP routes plus literal frontend API calls;
- JSON Schema, Prisma, and SQL schema artifacts plus literal schema references;
- intent-index journeys and their declared tests;
- CODEOWNERS or repository-declared ownership fallbacks;
- repository-declared protected security and authority boundaries.

Impact traversal follows downstream dependency direction. Package, owner, security, and journey nodes are contextual and may not act as uncontrolled hubs. A journey expands to its implementation and tests only when it is the sole available task seed. Route implementations expand through their API contract to statically discovered consumers.

All discovery and traversal limits are explicit. Exceeding `maxSourceFiles`, `maxNodes`, or `maxImpactNodes` fails closed. The engine never imports project code, starts a runtime, executes verification, approves architecture, or modifies a baseline.

## Consequences

- A task receives a reviewable blast radius and protected verification requirements before execution.
- Static analysis remains fast enough for repository CI and portable to consuming repositories.
- Dynamic calls, generated code, aliases, reflection, runtime dependency injection, and undocumented ownership may remain unresolved; these are limitations, not inferred edges.
- Protected boundary results indicate that declared human authority is required. They are not approval receipts.
- The graph complements architecture documents and ADRs. It does not replace them as authority.

## Rejected Alternatives

- A graph database was rejected because the bounded repository graph does not require a service or parallel state authority.
- Runtime instrumentation was rejected as a default because it executes repository code and cannot be safe during discovery.
- Fully bidirectional traversal was rejected because packages and journeys turned small changes into repository-wide impact sets.
- Unbounded best-effort output was rejected because partial graphs must not be reported as complete.
