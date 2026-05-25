---
name: session-learning
description: Capture session observations through opt-in hooks, inspect recent Codex or Claude sessions for repeated workflows, and promote stable lessons into AGENTS.md, README.md, skills, custom subagent recommendations, or docs without letting hooks mutate canonical project files directly.
---

# Session Learning

## Overview
Use this skill at the end of meaningful sessions, after a complex task succeeds, after a user correction, when repeated errors reveal a reusable workflow, or when the user asks to inspect recent sessions for skill or custom subagent opportunities. The goal is to turn session experience into durable project knowledge without polluting canonical docs.

This skill borrows four concepts from Hermes-style agents:
- **Small memory**: only stable rules belong in always-loaded context.
- **Session evidence**: raw observations stay searchable outside the prompt.
- **Procedural memory**: repeated workflows become skills.
- **Role memory**: bounded specialist roles become custom subagent recommendations.
- **Curator pass**: stale, duplicate, or weak candidates are archived instead of accumulating forever.

## Storage Contract
Learning artifacts live under the active project root:

```text
.omx/learning/
  observations.jsonl
  candidates/
  promoted/
  archive/
```

Generated observations and candidates are ignored by git by default. Promote only the distilled rule, workflow, or document change that is worth keeping.

Hook install scope and promotion scope are intentionally separate:
- **Hook install scope** decides which sessions are observed (`project` or `global`).
- **Promotion scope** decides where a reviewed lesson should live (`project`, `workspace`, `user-global`, `skill`, `subagent`, or `archive`).

Even global hooks write observations under the active project's `.omx/learning` directory. Global promotion remains advisory until a human or explicit follow-up task edits a durable global policy file.

## Project Hook Install
After installing this skill into a project, preview project-scoped hook registration:

```bash
python3 .agents/skills/session-learning/scripts/install_hooks.py
```

Apply the hook registration:

```bash
python3 .agents/skills/session-learning/scripts/install_hooks.py --apply
```

Install hooks globally for every project:

```bash
python3 .agents/skills/session-learning/scripts/install_hooks.py --scope global --apply
```

Remove only the hooks registered for this project:

```bash
python3 .agents/skills/session-learning/scripts/install_hooks.py --uninstall --apply
```

Remove the global hook registration:

```bash
python3 .agents/skills/session-learning/scripts/install_hooks.py --scope global --uninstall --apply
```

The installer updates Codex and Claude hook config files. Project-scoped registrations carry `SESSION_LEARNING_SCOPE_ROOT=<project-root>`, so events outside that project are skipped. Global registrations omit that scope root and write observations under each active project's `.omx/learning` directory.

Inspect current registration without writing config:

```bash
python3 .agents/skills/session-learning/scripts/install_hooks.py --status
python3 .agents/skills/session-learning/scripts/install_hooks.py --scope global --status
```

## Hook Capture
The opt-in hook adapter is:

```bash
bash skills/session-learning/hooks/observe.sh prompt
bash skills/session-learning/hooks/observe.sh pre
bash skills/session-learning/hooks/observe.sh post
bash skills/session-learning/hooks/observe.sh stop
bash skills/session-learning/hooks/observe.sh pre-compact
bash skills/session-learning/hooks/observe.sh post-compact
```

Hooks must only write `.omx/learning` artifacts. They must not edit `AGENTS.md`, `README.md`, `skills/*`, or other canonical project files.

## Ad Hoc Session Pattern Scan
When the user asks to inspect recent Codex or Claude sessions for repeated workflows, skill candidates, or custom subagent candidates:

1. Start from summaries, learning candidates, or usage dashboards before reading raw session logs.
2. If raw logs are needed, report only pattern summaries. Do not quote prompts, tool arguments, outputs, secrets, or long conversation excerpts.
3. Look for repeated manual work that already has a future trigger, not just frequent topics.
4. Prefer updating an existing skill over adding a nearby duplicate.
5. Recommend a custom subagent only when the pattern is a bounded role, recurring investigation, review pass, or research task that can produce an independent deliverable.
6. Create or update only the useful artifacts the user asked for; otherwise return a short recommendation list.

Triage repeated work this way:

- Use `skill` for reusable workflows with steps, files, commands, scripts, validation, or recurring artifact formats.
- Use `subagent` for narrow roles such as CI failure triage, PR review, changelog drafting, release-readiness review, debugging investigation, test triage, or source research.
- Use `project`, `workspace`, or `user-global` for durable instructions or preferences rather than procedural execution.
- Use `archive` for one-off tasks, weak signals, duplicates, or patterns already covered well by an existing skill.

## Review Workflow
1. Read recent `.omx/learning/candidates/*.md`.
2. Classify each candidate:
   - `project`: stable project instruction future agents must follow, usually `AGENTS.md`, `README.md`, or project docs.
   - `workspace`: multi-repo or root/child-repo operating rules for the current workspace.
   - `user-global`: user-wide preferences or policies that apply across projects, usually a global Codex/Claude policy surface.
   - `skill`: reusable procedural workflow that belongs in `skills/<name>/SKILL.md`.
   - `subagent`: bounded specialist role, recurring investigation, review pass, or research task that should become a custom subagent definition or prompt.
   - `archive`: weak, stale, duplicate, or too session-specific.
3. Promote only candidates with concrete evidence and a clear future trigger.
4. Record promoted candidates under `.omx/learning/promoted/` when useful.

Preview promotion routing:

```bash
python3 skills/session-learning/scripts/review_candidates.py --roots .
python3 skills/session-learning/scripts/review_candidates.py --roots /path/to/project-a /path/to/project-b --since-days 30
```

The review script prints recommendations only. It must not edit canonical project files.

## Promote Criteria
Promote when at least one is true:
- The user explicitly corrected the agent and the correction should apply again.
- A non-trivial workflow succeeded after errors or dead ends.
- The same repo-specific convention appeared repeatedly.
- A future agent would waste time without the lesson.

Do not promote:
- One-off file paths or temporary runtime state.
- Facts already obvious from source or README.
- Broad preferences that do not name a concrete trigger.
- Raw logs, secrets, or long conversation excerpts.

Promotion scope defaults:
- Use `project` for repo-specific commands, routes, schemas, tests, build steps, or conventions.
- Use `workspace` for root coordination rules, child-repo autonomy, or cross-repo boundaries.
- Use `user-global` for durable personal preferences that should affect future Codex/Claude sessions everywhere.
- Use `skill` when the reusable lesson is mostly procedural and has a clear trigger.
- Use `subagent` when the lesson is a recurring bounded role or research/review job with a clear output contract.
- Use `archive` when the candidate lacks a future trigger, duplicates an existing rule, or only records temporary state.

## Curator Workflow
Run a curator pass periodically:
1. Archive duplicate candidates.
2. Archive candidates older than 30 days with no promotion signal.
3. Merge near-duplicate workflow candidates into one stronger candidate.
4. Keep canonical docs compact; prefer patching existing rules over adding nearby duplicates.

## Verification
- Run `python3 skills/session-learning/scripts/test_learning_observer.py`.
- Run `python3 skills/session-learning/scripts/test_install_hooks.py`.
- Run `python3 skills/session-learning/scripts/test_review_candidates.py`.
- Run `git diff --check`.
- Confirm new hook code does not contain machine-specific paths from unrelated projects.
