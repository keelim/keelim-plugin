# Codex-Only SkillOpt PoC

This harness trains and evaluates `skills/agent-instructions-improver/SKILL.md`
with SkillOpt while routing every model call through the local `codex` CLI.

## Boundary

- Optimizer backend: `codex_chat`, a local overlay that calls `codex exec`.
- Target backend: upstream SkillOpt `codex_exec`.
- Auth: existing Codex CLI login only.
- Output root: `.skillopt/outputs/`, ignored by git.
- Data root: `.skillopt/data/agent-instructions-improver-v1/`, ignored by git.

Do not use Claude, Anthropic keys, OpenAI API keys, Azure keys, Qwen, MiniMax, or
local vLLM for this PoC. The runner removes those environment variables before a
training subprocess is started.

## Runtime Matrix

```bash
OPTIMIZER_BACKEND=codex_chat
TARGET_BACKEND=codex_exec
CODEX_EXEC_PATH=codex
CODEX_EXEC_SANDBOX=workspace-write
CODEX_EXEC_APPROVAL_POLICY=never
CODEX_EXEC_NETWORK_ACCESS=false
```

The optimizer overlay writes the prompt into a temporary run directory and reads
the final response from `codex exec --output-last-message`. If that final response
is empty or the CLI fails, the runner stops instead of falling back to another
model.

## Commands

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_agent_instructions.py score-fixture
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_agent_instructions.py curate --dry-run --limit 20
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_agent_instructions.py prepare --check
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_agent_instructions.py train-codex --dry-run
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_agent_instructions.py doctor-codex
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_agent_instructions.py inspect-run
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_agent_instructions.py promote --dry-run
```

`prepare` without `--check` clones SkillOpt into `.skillopt/SkillOpt`, creates an
isolated Python workspace with `uv --cache-dir .skillopt/uv-cache`, copies this
overlay, and patches upstream backend dispatch for `codex_chat`.

`train-codex` without `--dry-run` runs a tiny pilot by default:

- `num_epochs=1`
- `batch_size=4`
- `workers=1`
- `limit=4`
- `train_size=4`
- `max_steps=1`
- curated split under `.skillopt/data/agent-instructions-improver-v1`

Before a live run, `train-codex` checks whether the effective `CODEX_HOME`
directory is writable. Restricted Codex App sandboxes may allow reading the
workspace while denying writes to `~/.codex/state_*.sqlite`; in that case
`codex exec` can fail every rollout and SkillOpt may otherwise treat those
failures as zero-score task results. Run live pilots from a surface that can use
the local Codex CLI login state, or pass `--allow-readonly-codex-home` only when
you intentionally want to observe the failure mode.

After a live run, `train-codex` inspects the run output. If any
`traceback.txt` files are present, the command exits non-zero instead of
silently accepting a blocked run.

Use `inspect-run` to summarize a completed run:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/skillopt_agent_instructions.py inspect-run \
  --run-root .skillopt/outputs/agent-instructions-improver/codex-only-pilot
```

## Promotion

`promote --dry-run` compares the newest `.skillopt/outputs/**/best_skill.md`
against `skills/agent-instructions-improver/SKILL.md` and prints a unified diff.
It never overwrites the production skill unless `--apply` is supplied.

Promotion should remain a human review step. A winning SkillOpt artifact can still
be too narrow, too verbose, or inconsistent with the shared skill collection.

For repo-wide candidate review across every plugin skill, use
`uv --cache-dir .skillopt/uv-cache run --python 3.12 python scripts/promote_plugin_skills.py promote`.
That script discovers SkillOpt `best_skill.md` artifacts per skill and can also
compare manually staged candidate `SKILL.md` files.
