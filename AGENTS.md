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

## Boundaries

- Keep workflows docs-first unless automation clearly improves repeatability.
- Do not put secrets, session logs, or one-off task status into skill files.
- Preserve this repo as a skill collection; avoid mixing unrelated workspace maintenance into skill changes.
