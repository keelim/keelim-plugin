#!/usr/bin/env python3
"""Check this repository's skills-only plugin contract and marketplace paths offline.

This is a deliberately narrow repository check, not a general JSON Schema engine.
The portable schema and upstream documentation are linked in README.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"{path.name}: expected a JSON object")
    return data


def validate(root: Path) -> int:
    root = root.resolve()
    manifest = read_object(root / "plugin.json")
    require(
        set(manifest) == {"$schema", "name", "version", "description", "author", "repository"},
        "plugin.json: unexpected or missing fields in the skills-only manifest",
    )
    require(manifest["$schema"] == SCHEMA_URL, "plugin.json: expected Agent Plugins 1.0.0 schema")
    require(manifest["name"] == "keelim-plugin", "plugin.json: unexpected plugin name")
    version = manifest["version"]
    require(isinstance(version, str) and SEMVER.fullmatch(version) is not None, "invalid SemVer")
    description = manifest["description"]
    require(isinstance(description, str) and bool(description.strip()), "description is required")
    require(
        manifest["author"] == {"name": "keelim", "url": "https://github.com/keelim"},
        "plugin.json: unexpected publisher metadata",
    )
    require(
        manifest["repository"] == "https://github.com/keelim/keelim-plugin",
        "plugin.json: unexpected repository",
    )
    for relative in (
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        "mcp.json",
        ".mcp.json",
        ".app.json",
        "hooks/hooks.json",
    ):
        require(not (root / relative).exists(), f"unexpected package component: {relative}")

    skills_root = root / "skills"
    require(skills_root.is_dir(), "missing root skills/ directory")
    skills = sorted(skills_root.glob("*/SKILL.md"))
    require(bool(skills), "package must include at least one skill")
    for skill in skills:
        require(skill.resolve().is_relative_to(root), f"skill escapes plugin root: {skill}")
        require(skill.is_file(), f"missing skill file: {skill}")

    market = read_object(root / ".agents/plugins/marketplace.json")
    require(set(market) == {"name", "interface", "plugins"}, "unexpected marketplace fields")
    require(market["name"] == "keelim-plugins", "unexpected marketplace name")
    require(market["interface"] == {"displayName": "Keelim Plugins"}, "invalid marketplace label")
    entries = market["plugins"]
    require(isinstance(entries, list) and len(entries) == 1, "expected one marketplace entry")
    entry = entries[0]
    require(isinstance(entry, dict), "invalid marketplace entry")
    require(set(entry) == {"name", "source", "policy", "category"}, "invalid entry fields")
    require(entry["name"] == manifest["name"], "marketplace/manifest name mismatch")
    require(entry["category"] == "Productivity", "invalid marketplace category")
    require(
        entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "marketplace must offer an optional install with explicit authentication policy",
    )
    source = entry["source"]
    require(isinstance(source, dict) and set(source) == {"source", "path"}, "invalid source")
    require(source["source"] == "local", "expected a local marketplace source")
    relative = source["path"]
    require(
        isinstance(relative, str) and relative.startswith("./"), "source.path must start with ./"
    )
    require((root / relative).resolve() == root, "source.path must resolve to the repository root")
    require((root / "catalog.json").is_file(), "preserve the separate generated skill catalog")
    return len(skills)


def main() -> int:
    try:
        count = validate(REPO_ROOT)
    except (OSError, ValueError) as exc:
        print(f"[verify-plugin] ERROR: {exc}")
        return 1
    print(f"[verify-plugin] valid portable manifest, marketplace, and {count} skill paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
