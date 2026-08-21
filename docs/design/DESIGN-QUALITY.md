# Design Quality

The canonical thresholds are `.design/quality/thresholds.json`.

The deterministic score is out of 100:

- accessibility: 25
- viewport containment: 25
- DOM and state assertions: 20
- governed visual drift: 20
- design-contract assertions: 10

Passing requires at least 90 and every mandatory gate: zero critical or serious axe violations, five required viewports, no containment failures, governed baselines within 0.005 pixel-diff ratio, all contract assertions, and no more than three repair iterations.

The drift score is separate and inverse: 0 means no measured drift; 100 is maximum bounded deterministic drift. Model visual review is stored as evidence and never converted into numeric truth.
