# Ticket Desk Rules

## Buckets
- `focus`: work that deserves attention today or is actively in progress.
- `next`: valid work that is not today's focus.
- `waiting`: work waiting on another person, approval, review, or upstream dependency.
- `blocked`: work that cannot proceed until a concrete blocker is removed.
- `monitoring`: work to watch, but not actively push.
- `ignored`: intentionally not processed by this desk. Always show a reason or note.

## Local Rule Fields
- `bucket`: one of the supported bucket names.
- `reason`: short reason shown near the ticket.
- `review_after`: date or short text for the next review point.
- `note`: freeform local context.

Rules may be either:

```json
{
  "tickets": {
    "ABC-1": {
      "bucket": "ignored",
      "reason": "owned by another team"
    }
  }
}
```

or:

```json
{
  "ABC-1": {
    "bucket": "monitoring",
    "reason": "watch dependency only"
  }
}
```

## JQL Starting Points
Use the user's actual project and identity when known. Otherwise keep queries conservative:

```text
assignee = currentUser() AND resolution = Unresolved ORDER BY priority DESC, updated DESC
watcher = currentUser() AND resolution = Unresolved ORDER BY updated DESC
project = ABC AND resolution = Unresolved ORDER BY status ASC, priority DESC
```

Do not write to Jira in v1. If the user asks to mutate Jira, stop and confirm that the scope has changed.

## Data JSON Contract
The reusable data file is what the HTML template consumes. The renderer can create it from Jira JSON:

```bash
python3 scripts/render_ticket_desk.py --tickets tickets.json --rules ticket-desk.rules.json --data-output ticket-desk.data.json
```

Minimum shape:

```json
{
  "title": "Jira Ticket Desk",
  "subtitle": "Read-only local view for ticket triage.",
  "generated_at": "2026-05-10 07:25 UTC",
  "buckets": [
    { "id": "focus", "title": "Focus" }
  ],
  "tickets": [
    {
      "key": "ABC-1",
      "summary": "Example ticket",
      "status": "In Progress",
      "assignee": "Keelim",
      "priority": "High",
      "due": "2026-05-12",
      "updated": "2026-05-10",
      "bucket": "focus",
      "labels": ["release"],
      "reason": "",
      "review_after": "",
      "note": ""
    }
  ]
}
```

Render the template from a data file:

```bash
python3 scripts/render_ticket_desk.py --data ticket-desk.data.json --output ticket-desk.html
```

The template consumes only the embedded JSON object. It must not read sibling JSON files at runtime, because secure local browsers may block file reads and the output must remain self-contained.

## Lazyweb Design Guidance
When Lazyweb is available, search desktop references such as:
- `desktop project management ticket dashboard triage board`
- `desktop task list priority status dashboard`
- `issue tracker backlog priority board`

Extract layout principles, not runtime assets. Good patterns for this desk:
- compact status summary across the top
- bucket columns or grouped sections that scan vertically
- visible reason chips for ignored and waiting tickets
- restrained colors with strong contrast for blocked and focus items
- dense metadata rows rather than marketing-style hero sections
- stable left navigation for buckets
- lightweight view tabs for board/focus/ignored modes

## Offline Validation
Before sharing the HTML path, check for:

```text
http://
https://
fetch(
XMLHttpRequest
WebSocket
script src
link href
@import
```

The generated HTML may contain inline `<script>` and `<style>` blocks. It must not load anything from outside the file.

After validation passes, open the generated HTML in a local browser or preview surface. If the environment cannot open files, report the absolute output path and make that limitation explicit.
