---
name: jira-ticket-desk
description: Read Jira tickets through Atlassian MCP, merge local handling rules for intentionally ignored or deferred work, optionally consult Lazyweb for desktop dashboard design references, and render a secure offline pure HTML personal ticket desk from a reusable template plus replaceable JSON data. Use when the user wants to review, triage, plan, or report on Jira tickets without mutating Jira.
---

# Jira Ticket Desk

## Overview
Use this skill to turn Jira tickets into a local operating desk. The workflow is read-only toward Jira: it may inspect tickets through Atlassian MCP, but it must not change status, labels, assignees, comments, or fields.

The final HTML must work in a secure offline environment. Lazyweb is only a design-reference source before template changes; never leave Lazyweb, Jira, CDN, font, image, or script URLs in the generated HTML.

## Workflow
1. Confirm whether an Atlassian MCP server is available in the current session.
   - If available, query only the tickets needed for the user's desk.
   - If unavailable, stop before claiming live Jira coverage and ask for a Jira export or MCP setup.
2. Normalize Jira issues into JSON with stable fields: `key`, `summary`, `status`, `assignee`, `priority`, `due`, `updated`, `project`, `issue_type`, `labels`, and optional `bucket`.
3. Load local rules when present. Prefer a local JSON file named `ticket-desk.rules.json`.
4. If Lazyweb is available, search desktop references for ticket triage boards, task priority lists, work dashboards, and status summary panels. Use the references for template layout ideas only.
5. Build or update reusable desk data JSON with `scripts/render_ticket_desk.py --data-output`.
6. Render the HTML by injecting that data JSON into `assets/ticket-desk-template.html`.
7. Validate the output HTML for offline constraints before presenting it.
8. Open the generated HTML for the user after validation. Prefer the Codex in-app browser or another available local browser preview for the output file; on macOS shell workflows, `open ticket-desk.html` is acceptable. If the environment cannot open files, return the absolute HTML path and say that opening was unavailable.

## Local Rules
Use local rules for tickets that should not be handled automatically. This makes intentional non-action visible instead of letting those tickets look forgotten.

Minimal JSON shape:

```json
{
  "tickets": {
    "PROJ-123": {
      "bucket": "ignored",
      "reason": "belongs to another owner",
      "review_after": "2026-05-31",
      "note": "Watch only if dependency changes."
    }
  }
}
```

Supported buckets are `focus`, `next`, `waiting`, `blocked`, `monitoring`, and `ignored`. Treat unknown bucket names as `next` unless the user explicitly asks for custom sections.

## Rendering
The normal repeated-use path is template plus data JSON:

```bash
python3 scripts/render_ticket_desk.py --tickets tickets.json --rules ticket-desk.rules.json --data-output ticket-desk.data.json
python3 scripts/render_ticket_desk.py --data ticket-desk.data.json --output ticket-desk.html
```

The first command can be run only when Jira data changes. The second command can be rerun whenever the user edits `ticket-desk.data.json` locally.

For a one-shot render:

```bash
python3 scripts/render_ticket_desk.py --tickets tickets.json --rules ticket-desk.rules.json --output ticket-desk.html
```

For a quick smoke test:

```bash
python3 scripts/render_ticket_desk.py --demo --data-output /tmp/jira-ticket-desk.data.json
python3 scripts/render_ticket_desk.py --data /tmp/jira-ticket-desk.data.json --output /tmp/jira-ticket-desk-demo.html
python3 scripts/render_ticket_desk.py --check-html /tmp/jira-ticket-desk-demo.html
open /tmp/jira-ticket-desk-demo.html
```

The renderer accepts either a Jira search response with `issues` or a plain array of issue objects. It intentionally omits remote URLs from the generated data and HTML.

## Template
The bundled template lives at `assets/ticket-desk-template.html`. It is inspired by Lazyweb references for Jira template galleries, Trello-style task boards, project-dashboard view tabs, and operations-dashboard KPI cards.

Do not edit runtime data directly into the template except through the `__TICKET_DESK_DATA__` placeholder. Use `--data` to inject JSON into a fresh output copy.

## Offline HTML Contract
Generated HTML must be a single file with inline CSS and inline JavaScript only. It must not contain:
- `http://` or `https://`
- external `script src` or `link href`
- CSS `@import`
- `fetch(`, `XMLHttpRequest`, or `WebSocket`
- remote images, fonts, analytics, or CDN assets

Use inline SVG or CSS for small visual indicators. If an input ticket includes remote URLs, keep them out of the HTML and show the issue key as text.

## References
Read `references/ticket-desk-rules.md` when you need the bucket definitions, data schema, JQL examples, design guidance, or offline validation checklist.
