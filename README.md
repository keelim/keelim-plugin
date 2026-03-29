# keelim-plugin

A personal skill collection for both Codex and Claude.

## Goals
- Keep each skill as a single source of truth under `skills/`
- Make the same skill folder usable from both Codex and Claude
- Prefer docs-first skills unless automation is clearly worth the maintenance cost

## Repository layout
- `skills/`: skill source folders
- `skills/<skill-name>/SKILL.md`: the main skill document
- `skills/<skill-name>/agents/openai.yaml`: optional Codex UI metadata

## Current skills
- `release-automation`: a date-based Android release workflow for updating `versionCode`, checking the release PR, and dispatching `app_deploy.yml` with `dry-run`, `confirm`, and `execute` modes
- `tech-post-maker`: a writing skill for first-person technical posts in a calm personal engineer voice, especially build logs, case studies, workflow write-ups, and series posts

## Install with the Vercel skills CLI

List the skills available from this repository:

```bash
npx skills add keelim/keelim-plugin --list
```

Install a specific skill for both Codex and Claude Code in the current project:

```bash
npx skills add keelim/keelim-plugin \
  --skill tech-post-maker \
  -a codex \
  -a claude-code \
  -y \
  --copy
```

This installs the skill into:
- `./.agents/skills/<skill-name>`
- `./.claude/skills/<skill-name>`

If you prefer the full GitHub URL form, this also works:

```bash
npx skills add https://github.com/keelim/keelim-plugin --list
```

## Manual install

### Codex
```bash
ln -s /Users/keelim/Desktop/keelim-plugin/skills/tech-post-maker ~/.agents/skills/tech-post-maker
```

### Claude
```bash
ln -s /Users/keelim/Desktop/keelim-plugin/skills/tech-post-maker ~/.claude/skills/tech-post-maker
```

## Notes
- The Vercel skills CLI flow was verified with both source formats:
  - `keelim/keelim-plugin`
  - `https://github.com/keelim/keelim-plugin`
- The repository still supports manual symlink installation.
- The current skills are intentionally docs-first, so the workflows stay easy to inspect and adapt.
