#!/usr/bin/env python3
"""Run repo-local validation for keelim-plugin without external test deps."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    print(f"[run-tests] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
    return proc.returncode


def unique(paths: list[Path]) -> list[Path]:
    return list(dict.fromkeys(path for path in paths if path.exists()))


def python_files() -> list[Path]:
    return unique(
        [
            *sorted((REPO_ROOT / "scripts").glob("*.py")),
            *sorted((REPO_ROOT / "evals" / "skillopt").glob("**/*.py")),
            *sorted((REPO_ROOT / "skills").glob("*/scripts/*.py")),
        ]
    )


def test_files() -> list[Path]:
    return unique(
        [
            *sorted((REPO_ROOT / "skills").glob("*/scripts/test_*.py")),
            *sorted((REPO_ROOT / "scripts").glob("test_*.py")),
            *sorted((REPO_ROOT / "evals" / "skillopt").glob("**/test_*.py")),
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-diff-check", action="store_true")
    args = parser.parse_args(argv)

    py_paths = [str(path.relative_to(REPO_ROOT)) for path in python_files()]
    checks: list[list[str]] = []
    if py_paths:
        checks.append([sys.executable, "-m", "py_compile", *py_paths])
    checks.extend([[sys.executable, str(path.relative_to(REPO_ROOT))] for path in test_files()])
    checks.extend(
        [
            ["bash", "scripts/verify-skills.sh"],
            ["node", "scripts/gen-catalog.mjs", "--check"],
        ]
    )
    if not args.skip_diff_check:
        checks.append(["git", "diff", "--check"])

    for cmd in checks:
        code = run(cmd)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
