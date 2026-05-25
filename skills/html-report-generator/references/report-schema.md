# HTML Report Block Model

The renderer accepts one JSON object with generic report fields. Keep the schema broad enough for many report types and avoid type-specific keys in the first pass.

Core fields:

- `title`: required report title.
- `subtitle`: optional short subtitle.
- `summary`: optional summary text.
- `metadata`: optional object of label/value pairs.
- `metrics`: optional array of `{ "label": "...", "value": "...", "note": "..." }`.
- `sections`: optional array of `{ "heading": "...", "body": "...", "items": [...] }`.
- `tables`: optional array of `{ "title": "...", "columns": [...], "rows": [[...]] }`.
- `findings`: optional array of `{ "severity": "info|low|medium|high|critical", "title": "...", "body": "..." }`.
- `appendix`: optional array of section-like objects.

All user-provided strings must be rendered as escaped text.

## Field Details

### `metadata`

Object values are rendered as label/value pairs. Keep values scalar when possible.

```json
{
  "metadata": {
    "Owner": "Platform",
    "Generated": "2026-05-25"
  }
}
```

### `metrics`

Use short labels and values suitable for cards.

```json
{
  "metrics": [
    { "label": "Open findings", "value": "4", "note": "2 high" }
  ]
}
```

### `sections` and `appendix`

Each section supports `heading`, `body`, and optional `items`.

```json
{
  "sections": [
    {
      "heading": "Summary",
      "body": "Main narrative text.",
      "items": ["First point", "Second point"]
    }
  ]
}
```

### `tables`

Use string-like cells. The renderer escapes every cell.

```json
{
  "tables": [
    {
      "title": "Checks",
      "columns": ["Name", "Result"],
      "rows": [["Offline validation", "Pass"]]
    }
  ]
}
```

### `findings`

Severity may be `info`, `low`, `medium`, `high`, or `critical`. Unknown severities render as `info`.

```json
{
  "findings": [
    {
      "severity": "high",
      "title": "Remote asset detected",
      "body": "Validation should fail before sharing."
    }
  ]
}
```

### `links`

References render as plain text, not anchors. Remote URLs are omitted so generated reports remain offline-safe.
