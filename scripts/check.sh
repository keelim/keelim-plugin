#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

UV_CACHE="${UV_CACHE:-.skillopt/uv-cache}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
UV=(uv --cache-dir "$UV_CACHE")

echo "[check] uv lock --check"
"${UV[@]}" lock --check

echo "[check] ruff check"
"${UV[@]}" run --python "$PYTHON_VERSION" --group dev ruff check scripts

echo "[check] ruff format --check"
"${UV[@]}" run --python "$PYTHON_VERSION" --group dev ruff format --check scripts

echo "[check] mypy"
"${UV[@]}" run --python "$PYTHON_VERSION" --group dev mypy

echo "[check] repo tests"
"${UV[@]}" run --python "$PYTHON_VERSION" --group dev python scripts/run-tests.py
