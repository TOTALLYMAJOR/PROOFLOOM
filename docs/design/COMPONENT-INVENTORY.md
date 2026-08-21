<!-- design-intelligence: derived-view -->
# Component Inventory

The generated component registry lives at `.design/memory/component-registry.json`.

`design-intelligence registry scan` is read-only. Add `--write` to update the canonical generated file while preserving validated dates, linked decisions, surfaces, and debt IDs for unchanged paths.

This utility repository owns no production frontend component library, so its local registry is intentionally empty. Tests prove scanning against the mature frontend fixture and discover `components/ui/Button.tsx`. Consuming repositories retain component authority.
