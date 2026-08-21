# Autonomous Design Department V2

V2 turns the five V1 skills into one governed learning and rendered-verification cycle.

## Authority sequence

1. Repository and product truth
2. Accepted portfolio and product rules
3. Relevant surface and component decisions
4. Active, unexpired exceptions
5. Current design contract
6. Deterministic rendered evidence
7. Model review evidence
8. Agent preference

The last item can inform a proposal. It cannot become law without implementation, validation, an outcome, and authorized promotion.

## Operating sequence

1. `design-intelligence assess --root <repo>`
2. `design-intelligence memory context --root <repo> --product <product> --surface <surface>`
3. `design-intelligence contract validate --input <contract.json>`
4. Implement only the contract's bounded change.
5. Run the consuming repo's browser tooling or `scripts/design/visual-qa.mjs`.
6. Run deterministic quality scoring and model visual review separately.
7. If deterministic repair is authorized, run at most three evidence-linked iterations.
8. Record accepted, rejected, or inconclusive outcomes before promoting a decision.

## Safety invariants

- Accessibility, safety, semantic correctness, and validated product requirements cannot be excepted away.
- Pixel difference is drift evidence, not aesthetic truth.
- A model finding is not a numeric score.
- Baselines change only through `baseline promote` and a human-authorized approval record.
- Repairs cannot touch baseline, threshold, test, migration, API, server, backend, architecture, or product-authority boundaries.
