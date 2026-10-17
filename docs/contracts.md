# Skill and tooling interfaces

Agent hosts consume `skills/<name>/SKILL.md` with `name`, `description`, and a six-boolean capabilities mapping. `agents/openai.yaml` is optional presentation metadata generally required by this repository's strict validation mode. Referenced resources must exist; discovery does not authorize executing every supported effect.

| Interface | Input | Output and failure |
| --- | --- | --- |
| `node scripts/gen-catalog.mjs` | Current skill front matter | Rewrites CATALOG.md/catalog.json; malformed input is a generation error |
| Same command with `--check` | Source metadata and saved catalogs | Reports drift without accepting stale catalogs as current |
| `bash scripts/verify-skills.sh --require-codex-meta` | Skill folders and metadata/resources | Validation result; missing metadata or invalid capability combinations fail |
| `scripts/promote_plugin_skills.py inventory` through uv | Existing source skills | Available promotion scope; no model call |
| `promote [--skill name] [--candidate path]` | Candidate workflow or optimizer output | Diff/comparison; production source changes only with explicit `--apply` |
| `bash scripts/check.sh` | Locked dev environment and repository sources | CI-equivalent local checks; first failing command stops successful completion |

Catalogs expose the same capabilities as their source. Installation by a symlink follows changes; CLI `--copy` produces a snapshot. Hook installers have preview and explicit apply paths; a local result cannot establish host hook execution or remote credential readiness.
