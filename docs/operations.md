# Local setup and verification

Use Python 3.12, uv, and Node. Prepare the repo-local ignored cache and pinned development tools:

```sh
uv --cache-dir .skillopt/uv-cache sync --python 3.12 --group dev
node scripts/gen-catalog.mjs
bash scripts/verify-skills.sh --require-codex-meta
node scripts/gen-catalog.mjs --check
```

Run Python entrypoints with `uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python <script> ...`. `bash scripts/check.sh` checks lock consistency, Ruff lint/format, mypy, Python tests, metadata, catalog drift, and whitespace before promotion.

Inspect promotion candidates without applying them:

```sh
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/promote_plugin_skills.py inventory
uv --cache-dir .skillopt/uv-cache run --python 3.12 --group dev python scripts/promote_plugin_skills.py promote
```

For an authorized application, supply the reviewed skill/candidate and `--apply`. Candidate preparation and optimizer execution can use model access and produce traces; they are not documentation checks. No shared database or product deployment is required to maintain this collection. Global installation, hook registration, and external personal-skill updates are separate requested actions.
