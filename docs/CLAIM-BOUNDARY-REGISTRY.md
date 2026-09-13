# Claim Boundary Registry

The claim-boundary registry is the reusable Design Intelligence contract extracted from QuietPilot's proof-boundary architecture. It lets a consuming repository declare which evidence is required before code, docs, UI copy, reports, task packets, or release notes may claim that a state is true.

This is not a product model. A repository supplies its own claim families, source authorities, wording, guards, and owners. Design Intelligence only validates and reports against those declared boundaries.

## What It Captures

A claim boundary records:

- the claim being made;
- the evidence required before the claim is allowed;
- wording that is safe when evidence exists;
- wording that is forbidden without stronger proof;
- affected surfaces;
- visibility boundaries;
- tests, scripts, policies, reviews, or runtime checks that should guard the claim;
- risk if the claim is overstated.

A stateful surface contract records:

- stage;
- known truth;
- missing or blocked proof;
- applicable proof boundary;
- next-action owner;
- next action;
- forbidden inference.

## QuietPilot Transfer

QuietPilot uses this pattern to prevent an inquiry from being treated as a quote, a sent proposal from being treated as acceptance, a checkout return from being treated as payment settlement, and local/development evidence from being treated as production readiness.

The reusable Design Intelligence version keeps the structure and discards the product-specific lifecycle. Other repositories can use the same contract for onboarding, billing, deployment, AI advisory claims, release readiness, data migration, customer access, governance approval, or design acceptance.

## Adoption Rules

- Existing repository authority outranks package defaults.
- A registry is evidence and policy, not implementation.
- A generated report must not promote a claim beyond the required evidence.
- Missing evidence should produce pending, blocked, unavailable, review-only, sample, or proof-needed language.
- Human approval, provider proof, local validation, release readiness, production readiness, and customer outcomes remain separate authorities.

## Schema

The schema is bundled at:

`design_intelligence/data/schemas/claim-boundary-registry.schema.json`

Use fixtures to prove the contract before wiring it into repository automation:

`tests/fixtures/claim-boundary-registry.json`
