---
name: codex-insights
description: Extract evidence-backed engineering insights from current or recent Codex and Claude sessions, produce concise reflections, detect repeated workflows, and route durable lessons to docs, skills, subagents, or project instructions. Use after completing a feature, complex bug fix, technology investigation, or multi-step task; when the user asks for insights, reflection, session patterns, weekly learnings, automation opportunities, or skill candidates; or when opt-in session observation hooks need installation or review.
capabilities:
  read_only: false
  local_write: true
  network_read: false
  external_write: false
  credentials: false
  hooks: true
---

# Codex Insights

## Overview

Turn completed engineering work into reusable knowledge. Analyze evidence rather than merely summarizing the conversation, then record only lessons with a clear future trigger.

Use the current session as the default scope. Write the report in English unless the user requests another language.

## Choose a Mode

- **Current session**: Extract insights from the active task. Use this for `$codex-insights`, `/insights`, or requests to reflect on work just completed.
- **Weekly**: Aggregate verified evidence from the last seven days, or from dates the user supplies. Include counts only when they can be measured from inspected sources.
- **Candidate review**: Route captured candidates to project, workspace, user-global, skill, subagent, or archive targets.
- **Hook management**: Preview, install, inspect, or remove the optional Codex and Claude observation hooks.

Do not broaden a current-session request into raw historical log analysis. Ask for or inspect additional history only when the requested mode requires it.

## Current-Session Workflow

1. Gather available evidence:
   - user requests and corrections in the active conversation
   - decisions, commands, errors, tool results, and verification already visible
   - changed files, tests, and git state when they are relevant and safe to inspect
   - `.omx/learning` summaries or candidates when the hooks are installed
2. Separate facts from interpretation. Label uncertain conclusions and omit unsupported details.
3. Identify lessons in these categories:
   - `Technical Insight`: behavior, API, debugging, testing, or implementation knowledge
   - `Workflow Insight`: repeated steps, friction, handoffs, or validation gaps
   - `Architecture Decision`: a durable choice and its tradeoff
   - `Skill Candidate`: a repeatable procedure with a future trigger
4. Prefer improving an existing skill, script, or instruction over proposing a nearby duplicate.
5. Produce one concise report. If there is no durable lesson, say so and do not create an empty artifact.

Treat a workflow as repeated only when at least two observed instances, prior candidates, or an explicit user statement support that claim. Never invent files, commands, errors, commit counts, time savings, or frequency estimates.

## Report Contract

Use the following sections, omitting only sections that truly do not apply:

```markdown
# Insight: <specific title>

- Date: YYYY-MM-DD
- Mode: current | weekly
- Classification: Technical Insight | Workflow Insight | Architecture Decision | Skill Candidate
- Confidence: high | medium | low

## Summary
## Evidence
## Key Learnings
## Problems Encountered
## Root Cause
## Better Workflow
## Automation Opportunities
## Skill Candidates
## Next Actions
```

Keep `Evidence` concrete and compact. Use `None observed` when a requested section has no support instead of manufacturing content.

For each skill candidate, include:

```markdown
### <candidate-name>
- Trigger: <future condition>
- Input: <required input>
- Minimal workflow: <short ordered steps>
- Expected value: <qualitative value unless measured>
- Confidence: high | medium | low
- Evidence: <observed support>
```

Do not generate or install another skill from a candidate unless the user explicitly asks. When asked, use the available skill-creation workflow and update an existing skill instead if it already covers the need.

## Save Artifacts

When the user invokes this skill for a repository reflection and local writes are allowed, save the report as:

```text
docs/insights/YYYY-MM-DD-<short-slug>.md
```

For weekly mode, use `docs/insights/YYYY-MM-DD-weekly-insights.md`. Avoid overwriting an unrelated file; choose a more specific slug if the path exists. If the user asks for chat-only output or the environment is read-only, render the same report in the response without writing a file.

Do not store raw transcripts, full tool payloads, secrets, credentials, personal data, or long command outputs in the report.

## Candidate Review and Promotion

Optional hooks store metadata-only observations and low-confidence candidates under the active project root:

```text
.omx/learning/
  observations.jsonl
  candidates/
  promoted/
  archive/
```

Keep this existing storage path for continuity. Hook output is evidence, not an automatic instruction change. Hooks must never edit `AGENTS.md`, `README.md`, `skills/*`, or other canonical files.

Observation records contain only categorical signals and project-scoped hashes. Never persist prompt text, tool inputs, tool outputs, error details, or free-form previews.

Start candidate review with summaries and candidate files. Read raw `observations.jsonl` only when needed, and report patterns rather than quoting private session content.

Preview deterministic routing:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 python skills/codex-insights/scripts/review_candidates.py --roots .
uv --cache-dir .skillopt/uv-cache run --python 3.12 python skills/codex-insights/scripts/review_candidates.py --roots /path/to/project-a /path/to/project-b --since-days 30
```

Route candidates as follows:

- `project`: repo-specific commands, routes, schemas, tests, or conventions
- `workspace`: multi-repo boundaries and root coordination rules
- `user-global`: stable preferences or policies that apply across projects
- `skill`: reusable procedures with clear triggers and validation
- `subagent`: bounded recurring research, review, debugging, or triage roles
- `archive`: weak, stale, duplicate, or session-specific observations

Promote only with concrete evidence and a future trigger. Periodically archive stale or duplicate candidates and merge near-duplicates before editing canonical documentation.

## Optional Hook Management

Preview project-scoped registration after installing the skill:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 python .agents/skills/codex-insights/scripts/install_hooks.py
```

Apply it only when the user requests hook installation:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 python .agents/skills/codex-insights/scripts/install_hooks.py --apply
```

Use `--scope global --apply` only for an explicit global request. Inspect with `--status`; remove with `--uninstall --apply`. Applying the new installer replaces matching legacy `session-learning` hook registrations so stale hook paths do not remain active.

The hook adapter supports `prompt`, `pre`, `post`, `stop`, `pre-compact`, and `post-compact` phases through `hooks/observe.sh`.

## Verification

Run the smallest relevant checks after changing this skill:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 python skills/codex-insights/scripts/test_insight_observer.py
uv --cache-dir .skillopt/uv-cache run --python 3.12 python skills/codex-insights/scripts/test_install_hooks.py
uv --cache-dir .skillopt/uv-cache run --python 3.12 python skills/codex-insights/scripts/test_review_candidates.py
bash scripts/verify-skills.sh --require-codex-meta
git diff --check
```
