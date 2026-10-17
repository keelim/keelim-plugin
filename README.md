# keelim-plugin

A personal skill collection for both Codex and Claude.

## Goals
- Keep each skill as a single source of truth under `skills/`
- Make the same skill folder usable from both Codex and Claude
- Prefer docs-first skills unless automation is clearly worth the maintenance cost

## Repository layout
- `plugin.json`: portable Agent Plugins 1.0.0 manifest; package version is independent of the Python tooling version
- `.agents/plugins/marketplace.json`: Codex marketplace exposing this repository as one plugin
- `skills/`: skill source folders
- `skills/<skill-name>/SKILL.md`: the main skill document with its required machine-readable capability contract
- `skills/<skill-name>/agents/openai.yaml`: optional Codex UI metadata
- `CATALOG.md`: generated human-readable skill catalog and install matrix
- `catalog.json`: generated machine-readable skill inventory for automation, separate from the Codex marketplace
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
- `codex-insights`: an evidence-backed session reflection workflow with concise insight reports, skill/subagent recommendations, candidate promotion, and optional metadata-only observation hooks
- `easy-release-note-video-pipeline`: an end-to-end release-note Shorts workflow for distinct motion concepts, Google Vids voiceover muxing, and verified private YouTube or Naver Clip drafts
- `eli5`: a standalone visual HTML explainer using ASD-STE100-inspired clarity principles while preserving conditions, risks, and evidence
- `html-report-generator`: a reusable offline HTML report foundation with generic block-model JSON, a stdlib renderer, template asset, and security validation
- `jira-ticket-desk`: a read-only Jira triage workflow that merges local ticket rules and renders a secure offline HTML desk from a reusable template plus JSON data
- `release-automation`: a date-based Android release workflow for updating `versionCode`, checking the release PR, and dispatching `app_deploy.yml` with `dry-run`, `confirm`, and `execute` modes
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

## Install the Codex plugin package

The root `plugin.json` follows the [portable Agent Plugins format](https://developers.openai.com/plugins/build/plugins#plugin-structure)
and its [versioned JSON Schema](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json).
Codex discovers the bundled skills in `skills/` automatically. The package adds
no MCP server, credentials, permissions, or automatic hooks. Skill-specific
effects and explicit setup requirements still apply, including the optional
`codex-insights` hook installation described below.

The [repo marketplace](https://developers.openai.com/plugins/build/plugins#marketplace-metadata)
at `.agents/plugins/marketplace.json` exposes one package, `keelim-plugin`, under
`keelim-plugins`. Its `source.path` is `./`, resolved from the repository root,
not from `.agents/plugins/`. `catalog.json` remains the generated inventory of
individual skills; Codex does not use it as a marketplace.

From a checkout containing these package files, register and inspect the source:

```bash
codex plugin marketplace add .
codex plugin marketplace list
codex plugin list --marketplace keelim-plugins --available --json
```

In Codex CLI versions that expose `codex plugin add` (tested with 0.160.0):

```bash
codex plugin add keelim-plugin@keelim-plugins
codex plugin list --marketplace keelim-plugins --json
```

These normal install commands update the current user's Codex configuration and
plugin cache. Alternatively, follow the official desktop flow: restart the
ChatGPT desktop app, open the Plugins Directory, choose **Keelim Plugins**, and
install **keelim-plugin**. Test the skills in a new conversation.

After a commit containing the marketplace and manifest is published to GitHub,
the remote registration command is `codex plugin marketplace add keelim/keelim-plugin`.
Use the local checkout command while testing unpublished changes. Register the
whole repository: a sparse checkout of only `.agents/plugins` omits the package.

### Package validation

`bash scripts/check.sh` also runs `scripts/verify_plugin.py` and its regression
tests. This offline repository contract check validates the selected manifest
fields, SemVer, skill paths, marketplace metadata, and source resolution. It is
separate from skill frontmatter/catalog checks and is not a general JSON Schema
validator. To check the manifest against the upstream schema as well:

```bash
plugin_schema="$(mktemp)"
curl -fsSL https://agent-plugins.org/schemas/1.0.0/plugin.schema.json -o "$plugin_schema"
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev --with jsonschema \
  python -c 'import json, sys; from jsonschema import Draft202012Validator; schema=json.load(open(sys.argv[1])); Draft202012Validator.check_schema(schema); Draft202012Validator(schema).validate(json.load(open("plugin.json")))' "$plugin_schema"
rm "$plugin_schema"
```

For an installation smoke test without changing personal settings or using
credentials, test a clean committed snapshot in a disposable home:

```bash
(
  set -euo pipefail
  plugin_test_root="$(mktemp -d)"
  mkdir -p "$plugin_test_root/source" "$plugin_test_root/home/.codex"
  git archive HEAD | tar -x -C "$plugin_test_root/source"
  printf 'cli_auth_credentials_store = "file"\n' > "$plugin_test_root/home/.codex/config.toml"
  codex_test() {
    env -i PATH="$PATH" HOME="$plugin_test_root/home" \
      CODEX_HOME="$plugin_test_root/home/.codex" codex "$@"
  }
  cd "$plugin_test_root/home" || exit 1
  codex_test plugin marketplace add "$plugin_test_root/source"
  codex_test plugin list --marketplace keelim-plugins --available --json
  codex_test plugin add keelim-plugin@keelim-plugins
  codex_test plugin list --marketplace keelim-plugins --json
  printf 'Temporary test files: %s\n' "$plugin_test_root"
)
```

Expect `keelim-plugin@keelim-plugins` with the manifest version and, after install,
`installed: true` and `enabled: true`. This proves package recognition and local
installation, not live execution of every skill or desktop UI behavior. No
authentication or hook setup is required for this package smoke test.

## Install individual skills with the Vercel skills CLI

This remains available for both Codex and Claude Code, independently of the
bundled Codex plugin. Choose one installation route per skill to avoid duplicate
entries in Codex.

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

For `codex-insights`, preview and apply project-scoped hook registration after installing the skill:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python .agents/skills/codex-insights/scripts/install_hooks.py
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python .agents/skills/codex-insights/scripts/install_hooks.py --apply
```

To install `codex-insights` hooks globally for every project:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python .agents/skills/codex-insights/scripts/install_hooks.py --scope global --apply
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
