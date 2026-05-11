#!/usr/bin/env bash
set -euo pipefail

PHASE="${1:-post}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "[session-learning] No python interpreter found; skipping observation" >&2
  exit 0
fi

"${PYTHON_BIN}" "${SKILL_ROOT}/scripts/learning_observer.py" --phase "${PHASE}"
