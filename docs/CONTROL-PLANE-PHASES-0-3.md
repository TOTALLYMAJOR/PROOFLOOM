# Development Control Plane Phases 0-3

## Purpose

The Phase 0-3 release turns the existing Design Intelligence repository into an installable, repository-native control-plane capability without making it the authority over a consuming product.

```text
request -> task packet -> bounded trusted context -> affected checks
        -> existing Design Intelligence / Playwright evidence -> audited result
```

The facade is deterministic. It does not select model providers, execute arbitrary task commands, merge code, deploy, change thresholds, promote baselines, or run repair automatically.

## Phase 0: reconcile before adding

`docs/CONTROL-PLANE-GAP-MAP.md` records every keep, adapt, add, and defer decision. The result preserves `.design` as the design authority and prevents a second backlog, design-memory store, baseline hierarchy, component registry, or E2E suite.

## Phase 1: manifest and health

`devctl.yaml` declares:

- root and adapter instructions;
- trust-ranked repository authorities;
- bounded-context limits and denied path patterns;
- task storage location;
- allowlisted verification command arrays;
- deterministic path-to-check rules;
- pointers to existing design memory, thresholds, baselines, scenario, and adoption evidence.

Core commands:

```bash
devctl init --root /path/to/repository
devctl validate --root /path/to/repository
devctl doctor --root /path/to/repository
```

`init` is additive and idempotent. It creates only `devctl.yaml`, `.dev/VERSION`, and task-state directories. `validate` fails on malformed declarations, path escapes, missing authorities, duplicate authorities, unknown checks, unsafe context limits, or missing design authorities. `doctor` also audits command availability and delegates memory, baseline, threshold, and adoption integrity to the existing engines.

## Phase 2: task, context, and impact

Create a task from a schema-backed JSON packet:

```bash
devctl task create --root /path/to/repository --input task.json
devctl task context TASK-ID --root /path/to/repository --format json
devctl impact TASK-ID --root /path/to/repository --changed src/App.tsx
devctl verify affected TASK-ID --root /path/to/repository --changed src/App.tsx
```

Context retrieval is bounded by both file count and total bytes. Required task context is considered first, duplicate paths inherit their highest declared trust, and the result contains repository-relative paths, reasons, trust ranks, byte counts, and SHA-256 identities. Secret-like paths, environment files, `.git`, and `node_modules` are never auto-loaded. A required denied or missing file fails the context packet.

Impact analysis combines task-required checks with manifest path rules. It explains every selected check and returns exact command arrays from the repository manifest. Phase 0-3 does not execute those commands; CI or the operator remains the execution authority.

## Phase 3: Design Intelligence integration

The facade delegates rather than reimplements:

```bash
devctl design inspect --root /path/to/repository
devctl design adopt "Improve proposal flow" --root /path/to/repository --image reference.png --analysis reference-analysis.json
devctl design adoption-audit --root /path/to/repository --input artifacts/design/adoptions/example/adoption-report.json
devctl visual plan TASK-ID --root /path/to/repository
devctl visual audit --root /path/to/repository --input artifacts/design/reports/example/qa-report.json
```

The adoption adapter uses the existing repository, memory, governance-receipt, and design-system checks. The visual adapter uses the existing quality scorer and governed-baseline auditor. Rendering remains in `scripts/design/visual-qa.mjs`; baseline changes remain human-governed; repairs remain separately allowlisted and capped at three iterations.

## Using it in another repository

1. Install the CLI from this checkout with `./scripts/install`.
2. Run `devctl init --root /path/to/product` once.
3. Review the generated `devctl.yaml`; add only real repository authorities and existing commands.
4. Run `devctl validate` and `devctl doctor`. Resolve missing authority or runtime findings instead of weakening the rules.
5. Create a task packet, retrieve bounded context, and inspect the affected-verification plan.
6. For frontend work, integrate the existing Design Intelligence memory and scenario only if the product does not already have equivalent authorities. If equivalents exist, point the manifest to them or add a thin adapter.
7. Run the repository's selected checks explicitly. Store evidence with `--output` when a durable JSON receipt is required.

## Bounded pilot

`TASK-DESIGN-CONTROL-PLANE-PILOT` targets the existing static Design QA Control Deck fixture and its governed five-viewport scenario. Its evidence proves manifest health, bounded context, deterministic impact selection, and visual quality/baseline auditing. It does not claim acceptance for QuotePilot, QuietPilot, or another production product.

## Deferred to later phases

- command execution policy, sandboxing, and approval gates;
- architecture-boundary graphing beyond deterministic path rules;
- durable handoffs and resumable multi-agent workflow state;
- release, merge, deployment, environment, security, and production authority;
- telemetry and cross-repository portfolio aggregation.
