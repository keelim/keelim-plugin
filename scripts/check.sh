#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

UV_CACHE="${UV_CACHE:-.skillopt/uv-cache}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
UV=(uv --cache-dir "$UV_CACHE")
STATIC_PATHS=(scripts skills/codex-insights/scripts)

echo "[check] uv lock --check"
"${UV[@]}" lock --check

echo "[check] ruff check"
"${UV[@]}" run --python "$PYTHON_VERSION" --group dev ruff check "${STATIC_PATHS[@]}"

echo "[check] ruff format --check"
"${UV[@]}" run --python "$PYTHON_VERSION" --group dev ruff format --check "${STATIC_PATHS[@]}"

echo "[check] mypy"
"${UV[@]}" run --python "$PYTHON_VERSION" --group dev mypy "${STATIC_PATHS[@]}"

echo "[check] repo tests"
"${UV[@]}" run --python "$PYTHON_VERSION" --group dev python scripts/run-tests.py
