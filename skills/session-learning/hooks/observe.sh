#!/usr/bin/env bash
set -euo pipefail

PHASE="${1:-post}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SKILL_ROOT}/../.." && pwd)"
UV_CACHE="${KEELIM_PLUGIN_UV_CACHE:-${REPO_ROOT}/.skillopt/uv-cache}"

if ! command -v uv >/dev/null 2>&1; then
  echo "[session-learning] uv not found; skipping observation" >&2
  exit 0
fi

if ! uv --cache-dir "${UV_CACHE}" run --python 3.12 python "${SKILL_ROOT}/scripts/learning_observer.py" --phase "${PHASE}"; then
  echo "[session-learning] uv observer run failed; skipping observation" >&2
  exit 0
fi
