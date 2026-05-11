---
name: session-usage-dashboard
description: Build a secure offline HTML dashboard and JSON summary from Codex and Claude session JSONL logs. Use when the user wants to track agent tool usage, skill invocations, subagent kinds, session harness activity, or usage counts for Codex/Claude runs without exposing raw prompts, tool arguments, or tool outputs.
---

# Session Usage Dashboard

## Overview
Use this skill to inspect the session an agent ran and produce a local usage dashboard. The dashboard helps operate a tighter harness by showing which tools, skills, and subagents were used, how often, and from which runtime.

The generated dashboard is intentionally local-only: a single HTML file with inline CSS and no network communication.

## Quick Start
Run the bundled renderer from the repository root:

```bash
python3 skills/session-usage-dashboard/scripts/build_session_usage_dashboard.py --current --cwd "$PWD" --out .omx/session-usage/current
```

Then open the generated dashboard locally:

```bash
open .omx/session-usage/current/dashboard.html
```

For explicit files:

```bash
python3 skills/session-usage-dashboard/scripts/build_session_usage_dashboard.py \
  --codex-session /path/to/codex-session.jsonl \
  --claude-session /path/to/claude-session.jsonl \
  --out .omx/session-usage/manual
```

The renderer writes:

- `dashboard.html`
- `summary.json`

Default output location is `.omx/session-usage/<timestamp>/`.

## Workflow
1. Prefer explicit `--codex-session` or `--claude-session` paths when the user names a session file.
2. Use `--current --cwd "$PWD"` when the user asks for the current or executed session.
3. Open `summary.json` when validating exact counts.
4. Confirm the generated `dashboard.html` remains offline-safe.
5. Open the generated `dashboard.html` locally for the user. Use `open <path-to-dashboard.html>` on macOS, or the available local browser/file viewer in other environments. Do not serve the file over HTTP just to view it.

## What To Count
- Codex tools: `response_item.payload.type=function_call` and `custom_tool_call`.
- Codex skills: explicit `$skill` and `[$skill]` mentions in user messages.
- Codex subagents: `session_meta.payload.thread_source=subagent` and `session_meta.payload.source.subagent`.
- Claude tools: message content items with `type=tool_use`.
- Claude skills: `attributionSkill`.
- Claude subagents: `attributionAgent`, `isSidechain`, and `Agent` tool input `subagent_type`.

Treat unknown or changed JSONL fields as warnings, not fatal errors.

## Security Contract
Never include raw prompts, user message bodies, tool arguments, command output, tool result content, stack traces, or model reasoning text in either output file.

Generated HTML must satisfy:

- No remote assets or external URLs.
- No CDN, external script, external stylesheet, iframe, or remote font.
- No `fetch`, `XMLHttpRequest`, WebSocket, EventSource, or beacon usage.
- Include a restrictive Content Security Policy with `connect-src 'none'`.
- Escape every rendered value.

If a generated dashboard fails the security checks, fix the script before sharing the output.

## Design Notes
Use `references/lazyweb-dashboard-notes.md` for dashboard layout guidance. Lazyweb may inform the design before generation, but do not embed Lazyweb image URLs, screenshot URLs, or any remote asset in the HTML.

## Verification
Run:

```bash
python3 skills/session-usage-dashboard/scripts/test_build_session_usage_dashboard.py
env PYTHONPYCACHEPREFIX=.omx/pycache python3 -m py_compile skills/session-usage-dashboard/scripts/build_session_usage_dashboard.py skills/session-usage-dashboard/scripts/test_build_session_usage_dashboard.py
python3 /Users/keelim/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/session-usage-dashboard
git diff --check
```
