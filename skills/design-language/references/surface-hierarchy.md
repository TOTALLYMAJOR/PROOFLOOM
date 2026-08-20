# Surface Hierarchy

Reason about interface layers in this order:

1. Application
2. Page
3. Region
4. Panel
5. Card
6. Interactive control
7. Overlay

Guidance:

- Each layer should communicate a different job.
- Avoid nesting cards repeatedly when a region, divider, or panel would communicate structure more clearly.
- High-frequency operational surfaces should privilege hierarchy and next action over ornament.
- Marketing surfaces can be more expressive, but still need one dominant action.
