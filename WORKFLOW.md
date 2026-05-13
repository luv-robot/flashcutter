# flashcutter Workflow

## Product Loop

```mermaid
flowchart TD
  A["Upload or import seed video"] --> B["Probe media metadata"]
  B --> C["Segment source footage"]
  C --> D["Choose operator-readable templates"]
  D --> E["Create one or more generation tasks"]
  E --> F["Build render plans"]
  F --> G["Queue or run FFmpeg renders"]
  G --> H["Probe rendered outputs"]
  H --> I["Review output versions"]
  I --> J{"Decision"}
  J --> K["Approve for ad testing"]
  J --> L["Request changes"]
  J --> M["Reject"]
  J --> N["Discard"]
  L --> D
```

## Operator Workflow

1. Add a seed video from upload or URL import.
2. Confirm the asset is ready and has media metadata.
3. Create or edit templates that describe creative goal, editing rules, delivery
   format, transformations, and review notes.
4. Create batch tasks for one seed video across several templates.
5. Queue tasks and monitor progress.
6. Open the review workspace.
7. Watch outputs, inspect metadata, and record approval or change feedback.

## Task State Flow

```mermaid
stateDiagram-v2
  [*] --> queued
  queued --> waiting
  waiting --> segmenting
  queued --> segmenting
  segmenting --> planning
  planning --> queued
  queued --> rendering
  rendering --> completed
  rendering --> failed
  segmenting --> failed
  planning --> failed
  waiting --> cancelled
```

## Review State Flow

```mermaid
stateDiagram-v2
  [*] --> pending_review
  pending_review --> approved
  pending_review --> needs_changes
  pending_review --> rejected
  pending_review --> discarded
  needs_changes --> approved
  needs_changes --> rejected
  rejected --> discarded
```
