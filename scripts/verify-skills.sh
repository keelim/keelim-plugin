#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

UV_CACHE="${UV_CACHE:-.skillopt/uv-cache}"
if command -v uv >/dev/null 2>&1; then
  uv --cache-dir "${UV_CACHE}" run --python 3.12 --group dev python scripts/verify_skills.py "$@"
elif command -v python3 >/dev/null 2>&1; then
  python3 scripts/verify_skills.py "$@"
elif command -v python >/dev/null 2>&1; then
  python scripts/verify_skills.py "$@"
else
  echo "[verify-skills] Python interpreter not found" >&2
  exit 1
fi
