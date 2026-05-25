# keelim-plugin Agent Guide

## Purpose

This repo is the source of truth for reusable local skills used by Codex and Claude.

## Skill Layout

- Keep each skill under `skills/<skill-name>/`.
- Every skill must include `SKILL.md`.
- Add `agents/openai.yaml` when the skill should appear cleanly in Codex UI surfaces.
- Use `references/`, `scripts/`, and `assets/` only when they directly support the skill.

## Maintenance Rules

- Update `README.md` `Current skills` whenever adding, renaming, or removing a skill.
- Prefer repo-local skill folders plus user-scope symlinks over duplicated copies.
- After changing skills, verify paths and run `git diff --check`.

## CodeGraph Search

When working from the `keelim-maestro` workspace root, use the root dispatcher
instead of a root aggregate graph:

```bash
bun run cg -- context keelim-plugin "<task>"
bun run cg -- query keelim-plugin <symbol>
bun run cg -- files keelim-plugin --max-depth 2
```

If an AI starts inside this repo directly, first check `/Users/keelim/Desktop/keelim-maestro`
for the dispatcher and prefer its child-targeted `--path` calls. Do not initialize
or rely on a workspace-root `.codegraph/` that mixes child repositories.

## Boundaries

- Keep workflows docs-first unless automation clearly improves repeatability.
- Do not put secrets, session logs, or one-off task status into skill files.
- Preserve this repo as a skill collection; avoid mixing unrelated workspace maintenance into skill changes.
