# Codex-Only Plugin Skill Improver

This harness runs tiny SkillOpt pilots for every skill in this repository while
routing every model call through the local `codex` CLI.

## Commands

All Python entrypoints must be run through `uv`:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_plugin_skills.py curate --skill all
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_plugin_skills.py train-codex --skill tech-post-maker --dry-run
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_plugin_skills.py run-all --apply-passing
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_plugin_skills.py inspect-all --fail-on-tracebacks
```

The runner writes generated data and model traces under `.skillopt/`, which is
ignored by git.

## Promotion

`run-all --apply-passing` applies only candidates that pass deterministic gates:
no tracebacks, no score regression, valid frontmatter, resource guidance
preserved, and bounded size changes. Rejected candidates stay in `.skillopt`
with their rejection reasons.
