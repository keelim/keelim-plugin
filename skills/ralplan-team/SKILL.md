---
name: ralplan-team
description: Use when implementing a non-trivial feature that should first be scoped with consensus planning via $ralplan and then executed in parallel with $team.
---

# Ralplan Team

## Overview
Use this skill when a feature should move in two phases:
1. scope and agree on the work with `$ralplan`
2. execute the approved plan with `$team`

This is for brownfield feature work where parallel execution is valuable, but only after the approach is locked.

## When to Use
Use this skill when:
- the task spans multiple files or layers
- there is an implementation choice that should be agreed before coding
- you want an explicit plan artifact in `.omx/plans/`
- you want tmux-based parallel delivery after approval

Do not use this skill when:
- the task is a tiny obvious fix
- the user wants planning only
- the user wants solo execution instead of team mode

## Phase 1 — Plan with `$ralplan`
1. Gather codebase facts first.
2. Create or reuse a context snapshot in `.omx/context/`.
3. Run `$ralplan` and produce an approved plan in `.omx/plans/`.
4. Make sure the plan includes:
   - requirements summary
   - acceptance criteria
   - implementation steps with file references
   - risks and mitigations
   - verification steps
   - ADR

## Phase 2 — Execute with `$team`
1. Launch `$team` against the approved plan path.
2. Split worker ownership cleanly.
3. Keep write scopes disjoint when possible.
4. Monitor with `omx team status <team-name>` and mailbox evidence.
5. Do not shut the team down until:
   - `pending=0`
   - `in_progress=0`
   - `failed=0` unless explicitly accepted
6. Run `omx team shutdown <team-name>` only after completion.

## Recommended Prompt Pattern
Start with:

```text
$ralplan <feature request>
```

Then execute with:

```text
$team execute the approved plan in .omx/plans/<plan-file>.md
```

For stronger team execution, include:
- exact plan path
- required constraints
- verification commands
- documentation update requirements such as `AGENTS.md`

## Examples
```text
$ralplan 새 루프 기능을 기획해줘
$team execute the approved plan in .omx/plans/2026-03-15-admin-loop-domain-drag-and-drop-plan.md
```

```text
$ralplan 공통 플로우 상세 dialog 개선 기획
$team execute the approved plan in .omx/plans/<approved-plan>.md with focused verification commands and AGENTS.md updates
```

## Operator Checklist
Before `$team`:
- confirm `tmux -V`
- confirm `$TMUX` is set
- confirm `command -v omx`
- confirm the plan file exists
- confirm the context snapshot exists
- inspect panes so duplicate HUD panes do not accumulate

During `$team`:
- verify startup evidence:
  - team name
  - worker panes
  - ACK messages in `mailbox/leader-fixed.json`
- if workers overlap on files, send an ownership correction message
- prefer mailbox/API coordination over ad-hoc pane typing

After `$team`:
- verify shutdown completed
- verify the team state directory is gone
- rerun final verification in the leader session before claiming success

## Good Defaults
- Prefer `$ralplan` for design-sensitive feature work.
- Prefer `$team` when work can be split into implementation / tests / review-doc lanes.
- Keep final verification in the leader session even if workers report success.
- Update inventory docs in the same change when behavior changes.

## Common Mistakes
- launching `$team` before the plan is stable
- vague team prompts without a plan path
- allowing multiple workers to edit the same file without correction
- trusting worker-reported test results without leader-side reruns
- shutting the team down while tasks are still active

## Output Expectation
A successful run leaves:
- one approved plan in `.omx/plans/`
- implemented code and tests
- leader-side verification evidence
- clean team shutdown with no stale worker panes
