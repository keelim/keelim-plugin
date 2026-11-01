#!/usr/bin/env python3
"""Regression checks for the Claude Code mod marketplace and mod package layout."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from verify_mods import MARKETPLACE, REPO_ROOT, validate


class ModValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(REPO_ROOT / ".claude-plugin", self.root / ".claude-plugin")
        shutil.copytree(REPO_ROOT / "mods", self.root / "mods")
        self.market = json.loads((self.root / MARKETPLACE).read_text(encoding="utf-8"))

    def write(self, relative: str, data: dict[str, Any]) -> None:
        (self.root / relative).write_text(json.dumps(data), encoding="utf-8")

    def test_valid_marketplace(self) -> None:
        self.assertEqual(validate(self.root), len(self.market["plugins"]))

    def test_invalid_source(self) -> None:
        name = self.market["plugins"][0]["name"]
        for source in ("./", ".", "./mods", f"mods/{name}", f"./mods/{name}/../..", None):
            with self.subTest(source=source):
                market = json.loads(json.dumps(self.market))
                market["plugins"][0]["source"] = source
                self.write(MARKETPLACE, market)
                with self.assertRaisesRegex(ValueError, "must use ./mods/"):
                    validate(self.root)

    def test_unlisted_mod(self) -> None:
        extra = self.root / "mods/unlisted/.claude-plugin"
        extra.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "do not match"):
            validate(self.root)

    def test_manifest_name_mismatch(self) -> None:
        name = self.market["plugins"][0]["name"]
        manifest = f"mods/{name}/.claude-plugin/plugin.json"
        original = json.loads((self.root / manifest).read_text(encoding="utf-8"))
        self.write(manifest, {**original, "name": "other"})
        with self.assertRaisesRegex(ValueError, "plugin.json name"):
            validate(self.root)

    def test_invalid_hooks_module(self) -> None:
        name = self.market["plugins"][0]["name"]
        hooks = f"mods/{name}/hooks/hooks.json"
        for modules, message in (
            ([], "exactly one"),
            (["./index.ts", "./other.ts"], "exactly one"),
            (["../../../escape.ts"], "escapes"),
            (["./index.json"], "suffix"),
            (["./missing.ts"], "missing hooks module"),
        ):
            with self.subTest(modules=modules):
                self.write(hooks, {"modules": modules})
                with self.assertRaisesRegex(ValueError, message):
                    validate(self.root)


if __name__ == "__main__":
    unittest.main()
