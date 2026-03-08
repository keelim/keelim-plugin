# keelim-skill

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
- `release-automation`: a date-based Android release workflow for updating `versionCode`, checking the release PR, and dispatching `app_deploy.yml` with `dry-run`, `confirm`, and `execute` modes.

## Install with the Vercel skills CLI

List the skills available from this repository:

```bash
npx skills add keelim/keelim-skill --list
```

Install `release-automation` for both Codex and Claude Code in the current project:

```bash
npx skills add keelim/keelim-skill \
  --skill release-automation \
  -a codex \
  -a claude-code \
  -y \
  --copy
```

This installs the skill into:
- `./.agents/skills/release-automation`
- `./.claude/skills/release-automation`

If you prefer the full GitHub URL form, this also works:

```bash
npx skills add https://github.com/keelim/keelim-skill --list
```

## Manual install

### Codex
```bash
ln -s /Users/keelim/Desktop/keelim-skill/skills/release-automation ~/.agents/skills/release-automation
```

### Claude
```bash
ln -s /Users/keelim/Desktop/keelim-skill/skills/release-automation ~/.claude/skills/release-automation
```

## Notes
- The Vercel skills CLI flow was verified with both source formats:
  - `keelim/keelim-skill`
  - `https://github.com/keelim/keelim-skill`
- Both formats successfully listed and installed `release-automation` for Codex and Claude Code.
- The repository still supports manual symlink installation.
- The first skill is intentionally docs-only, so the workflow stays easy to inspect and adapt.
