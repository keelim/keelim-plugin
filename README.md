# keelim-plugin

A personal skill collection for both Codex and Claude.

## Goals
- Keep each skill as a single source of truth under `skills/`
- Make the same skill folder usable from both Codex and Claude
- Prefer docs-first skills unless automation is clearly worth the maintenance cost

## Repository layout
- `skills/`: skill source folders
- `skills/<skill-name>/SKILL.md`: the main skill document with its required machine-readable capability contract
- `skills/<skill-name>/agents/openai.yaml`: optional Codex UI metadata
- `CATALOG.md`: generated human-readable skill catalog and install matrix
- `catalog.json`: generated machine-readable skill catalog for automation
- `scripts/`: catalog generation, skill validation, promotion, and SkillOpt entrypoints
- `evals/skillopt/`: SkillOpt pilot fixtures and test harnesses

## Current skills

The bullet list below is a compact README orientation. The canonical
user-facing trigger and catalog description for each skill lives in that skill's
`SKILL.md` frontmatter and is regenerated into `CATALOG.md` / `catalog.json`.

Every skill also declares these boolean capabilities in frontmatter:
`read_only`, `local_write`, `network_read`, `external_write`, `credentials`,
and `hooks`. The generated catalogs expose the same values so an agent or
operator can inspect side-effect and trust requirements before invocation.
`read_only: true` cannot be combined with local writes, external writes, or
hooks; `scripts/verify_skills.py` enforces the complete schema.

- `agent-instructions-improver`: an audit-and-improve workflow for AGENTS.md and related agent instruction files, including durable session-to-AGENTS.md updates, that reports quality findings before proposing targeted changes
- `codebase-codemap`: a source-led repository mapping workflow with a stdlib generator for project-named agent codemaps
- `html-report-generator`: a reusable offline HTML report foundation with generic block-model JSON, a stdlib renderer, template asset, and security validation
- `jira-ticket-desk`: a read-only Jira triage workflow that merges local ticket rules and renders a secure offline HTML desk from a reusable template plus JSON data
- `release-automation`: a date-based Android release workflow for updating `versionCode`, checking the release PR, and dispatching `app_deploy.yml` with `dry-run`, `confirm`, and `execute` modes
- `session-learning`: a conservative Hermes-inspired workflow for hook-based observations, ad hoc session pattern scans, skill/subagent recommendations, promotion, and curator cleanup
- `session-usage-dashboard`: a Codex/Claude session analyzer that renders offline HTML and JSON usage dashboards for tools, skills, and subagents
- `tech-post-maker`: a writing skill for first-person technical posts in a calm personal engineer voice, especially build logs, case studies, workflow write-ups, and series posts

## Prerequisites

- Python 3.12, matching `pyproject.toml`
- `uv` for Python entrypoints and pinned dev tooling
- Node.js for `scripts/gen-catalog.mjs`
- `npx` for Vercel skills CLI install flows

## Repo-local validation

Run the CI-equivalent local check before promoting skill, eval, or tooling
changes:

```bash
bash scripts/check.sh
```

The check verifies `uv.lock`, runs ruff, checks formatting, runs mypy, executes
the bundled Python tests, validates skill metadata, checks generated catalog
drift, and finishes with `git diff --check`.

After changing any skill folder, frontmatter, bundled resource, or README skill
list, refresh and verify the generated catalog:

```bash
node scripts/gen-catalog.mjs
node scripts/gen-catalog.mjs --check
bash scripts/verify-skills.sh --require-codex-meta
git diff --check
```

Install or refresh the pinned development tools with:

```bash
uv --cache-dir .skillopt/uv-cache sync --python 3.12 --group dev
```

All local Python entrypoints in this repo should be run through `uv`:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python <script> ...
```

The repo-local uv cache is intentionally ignored. To inspect or prune it:

```bash
du -sh .skillopt/uv-cache
uv --cache-dir .skillopt/uv-cache cache prune
```

## Contributing skill changes

When adding or renaming a skill:

1. Create or move `skills/<skill-name>/SKILL.md` with frontmatter `name` matching the folder, a concise `description`, and all six boolean `capabilities` fields.
2. Add `agents/openai.yaml` when the skill should be visible in Codex UI surfaces.
3. Keep supporting files inside that skill's `references/`, `scripts/`, `assets/`, `examples/`, or `hooks/` directories.
4. Update the README `Current skills` list only as a compact orientation; keep the `SKILL.md` frontmatter as the catalog source of truth.
5. Run `node scripts/gen-catalog.mjs`, `bash scripts/verify-skills.sh --require-codex-meta`, `node scripts/gen-catalog.mjs --check`, and `git diff --check`.

## Promote skills

Use `scripts/promote_plugin_skills.py` to route every plugin skill through the
same reviewable promotion path. The script never calls a model; it compares
candidate `SKILL.md` files or SkillOpt `best_skill.md` artifacts against the
current `skills/<name>/SKILL.md`, preserves frontmatter when needed, and applies
only when `--apply` is passed.

List the skills in scope:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/promote_plugin_skills.py inventory
```

Compare all available candidates without modifying production skills:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/promote_plugin_skills.py promote
```

For an end-to-end no-op smoke pass across every skill, stage the current skill
files into ignored candidate storage and require one candidate per skill:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/promote_plugin_skills.py stage-current --run-id all-skills-smoke
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/promote_plugin_skills.py promote \
  --candidate-root .skillopt/promote-candidates/all-skills-smoke \
  --require-candidates
```

Promote one reviewed candidate after inspecting the diff:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/promote_plugin_skills.py promote \
  --skill tech-post-maker \
  --candidate /path/to/reviewed/SKILL.md

uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/promote_plugin_skills.py promote \
  --skill tech-post-maker \
  --candidate /path/to/reviewed/SKILL.md \
  --apply
```

SkillOpt-generated candidates are picked up automatically from
`.skillopt/outputs/<skill>/**/best_skill.md`. Keep `.skillopt/` ignored; it may
contain model traces, split data, reports, and smoke candidates.

## Codex-only SkillOpt

Use `scripts/skillopt_plugin_skills.py` for the 8-skill Codex-only tiny pilot.
It curates per-skill redacted splits, runs SkillOpt with a local `codex_chat`
optimizer overlay plus upstream `codex_exec` target evaluation, and applies only
the candidates that pass deterministic promotion gates.

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/skillopt_plugin_skills.py prepare --check
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/skillopt_plugin_skills.py curate --skill all --dry-run
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/skillopt_plugin_skills.py run-all --dry-run
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/skillopt_plugin_skills.py run-all --apply-passing --num-epochs 1 --batch-size 4 --workers 1 --max-steps 1
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/skillopt_plugin_skills.py inspect-all --fail-on-tracebacks
```

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

`--copy` creates project-local snapshots. Re-run the CLI install command after
upstream skill changes, or use manual symlinks while actively developing against
this checkout.

For `session-learning`, preview and apply project-scoped hook registration after installing the skill:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python .agents/skills/session-learning/scripts/install_hooks.py
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python .agents/skills/session-learning/scripts/install_hooks.py --apply
```

To install `session-learning` hooks globally for every project:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python .agents/skills/session-learning/scripts/install_hooks.py --scope global --apply
```

If you prefer the full GitHub URL form, this also works:

```bash
npx skills add https://github.com/keelim/keelim-plugin --list
```

## Manual install

Run these commands from the repository root. Symlinks keep the installed skill
attached to the local `skills/` source tree, while CLI `--copy` installs a
snapshot that must be refreshed explicitly.

### Codex
```bash
ln -s "$(pwd)/skills/tech-post-maker" ~/.agents/skills/tech-post-maker
```

### Claude
```bash
ln -s "$(pwd)/skills/tech-post-maker" ~/.claude/skills/tech-post-maker
```

## Notes
- The Vercel skills CLI flow was verified with both source formats:
  - `keelim/keelim-plugin`
  - `https://github.com/keelim/keelim-plugin`
- The repository still supports manual symlink installation.
- The current skills are intentionally docs-first, so the workflows stay easy to inspect and adapt.
