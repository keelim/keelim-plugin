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
- `codebase-codemap`: a source-led repository mapping workflow with a stdlib generator for project-named agent codemaps
- `jira-ticket-desk`: a read-only Jira triage workflow that merges local ticket rules and renders a secure offline HTML desk from a reusable template plus JSON data
- `release-automation`: a date-based Android release workflow for updating `versionCode`, checking the release PR, and dispatching `app_deploy.yml` with `dry-run`, `confirm`, and `execute` modes
- `session-learning`: a conservative Hermes-inspired workflow for hook-based session observations, learning candidates, promotion, and curator cleanup
- `session-usage-dashboard`: a Codex/Claude session analyzer that renders offline HTML and JSON usage dashboards for tools, skills, and subagents
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

For `session-learning`, preview and apply project-scoped hook registration after installing the skill:

```bash
python3 .agents/skills/session-learning/scripts/install_hooks.py
python3 .agents/skills/session-learning/scripts/install_hooks.py --apply
```

To install `session-learning` hooks globally for every project:

```bash
python3 .agents/skills/session-learning/scripts/install_hooks.py --scope global --apply
```

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
