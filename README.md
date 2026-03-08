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

## Installation

### Codex
```bash
ln -s /Users/keelim/Desktop/keelim-skill/skills/release-automation ~/.agents/skills/release-automation
```

### Claude
```bash
ln -s /Users/keelim/Desktop/keelim-skill/skills/release-automation ~/.claude/skills/release-automation
```

## Notes
- This repository currently uses manual symlink installation.
- The first skill is intentionally docs-only, so the workflow stays easy to inspect and adapt.
