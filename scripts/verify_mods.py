#!/usr/bin/env python3
"""Check the Claude Code mod marketplace and each mod's package layout offline.

Mods are opt-in function-hook plugins under mods/<name>/. They stay separate from
the skills-only root package that scripts/verify_plugin.py guards. This check covers
static packaging only; `claude plugin validate` and `claude plugin test` are the
engine's own checks and run where the Claude Code CLI is installed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from verify_plugin import SEMVER, read_object, require

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ".claude-plugin/marketplace.json"
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MODULE_SUFFIXES = {".ts", ".tsx", ".jsx", ".js", ".mjs", ".cjs", ".mts", ".cts"}


def validate_mod(root: Path, name: str) -> None:
    mod = root / "mods" / name
    manifest = read_object(mod / ".claude-plugin/plugin.json")
    require(manifest.get("name") == name, f"mods/{name}: plugin.json name must be {name!r}")
    version = manifest.get("version")
    require(
        isinstance(version, str) and SEMVER.fullmatch(version) is not None,
        f"mods/{name}: invalid SemVer",
    )
    description = manifest.get("description")
    require(
        isinstance(description, str) and bool(description.strip()),
        f"mods/{name}: description is required",
    )

    hooks = read_object(mod / "hooks/hooks.json")
    modules: Any = hooks.get("modules")
    require(
        isinstance(modules, list) and len(modules) == 1 and isinstance(modules[0], str),
        f"mods/{name}: hooks/hooks.json must name exactly one hooks module",
    )
    module = (mod / "hooks" / modules[0]).resolve()
    require(module.is_relative_to(mod.resolve()), f"mods/{name}: hooks module escapes the mod")
    require(module.suffix in MODULE_SUFFIXES, f"mods/{name}: unsupported hooks module suffix")
    require(module.is_file(), f"mods/{name}: missing hooks module {modules[0]}")


def validate(root: Path) -> int:
    root = root.resolve()
    market = read_object(root / MARKETPLACE)
    require(market.get("name") == "keelim-mods", f"{MARKETPLACE}: unexpected marketplace name")
    entries: Any = market.get("plugins")
    require(isinstance(entries, list) and bool(entries), f"{MARKETPLACE}: list at least one mod")

    listed: list[str] = []
    for entry in entries:
        require(isinstance(entry, dict), f"{MARKETPLACE}: invalid entry")
        name = entry.get("name")
        require(isinstance(name, str) and NAME.fullmatch(name) is not None, "invalid mod name")
        source = entry.get("source")
        # A relative source keeps the mod read from this checkout; "./" would list the
        # skills root as a hooks plugin.
        require(source == f"./mods/{name}", f"{MARKETPLACE}: {name} must use ./mods/{name}")
        listed.append(name)
    require(len(listed) == len(set(listed)), f"{MARKETPLACE}: duplicate mod entry")

    mods_root = root / "mods"
    present = sorted(
        path.name
        for path in mods_root.iterdir()
        if path.is_dir() and (path / ".claude-plugin").exists()
    )
    require(sorted(listed) == present, f"{MARKETPLACE}: entries {listed} do not match {present}")
    for name in listed:
        validate_mod(root, name)
    return len(listed)


def main() -> int:
    try:
        count = validate(REPO_ROOT)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[verify-mods] ERROR: {exc}")
        return 1
    print(f"[verify-mods] valid mod marketplace and {count} mod package(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
