#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

UV_CACHE="${UV_CACHE:-.skillopt/uv-cache}"
if ! command -v uv >/dev/null 2>&1; then
  echo "[verify-skills] uv is required; direct python/python3 fallback is disabled" >&2
  exit 1
fi

uv --cache-dir "${UV_CACHE}" run --python 3.12 --group dev python scripts/verify_skills.py "$@"
