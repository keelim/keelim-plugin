#!/usr/bin/env python3
"""Regression checks for plugin discovery metadata and path resolution."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from verify_plugin import REPO_ROOT, validate


class PluginValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for relative in ("plugin.json", ".agents/plugins/marketplace.json", "catalog.json"):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / relative, destination)
        skill = self.root / "skills/example/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: example\ndescription: Example skill.\n---\n", encoding="utf-8")

    def write(self, relative: str, data: dict[str, Any]) -> None:
        (self.root / relative).write_text(json.dumps(data), encoding="utf-8")

    def test_valid_package(self) -> None:
        self.assertEqual(validate(self.root), 1)

    def test_invalid_manifest(self) -> None:
        original = json.loads((self.root / "plugin.json").read_text())
        for key, value in (
            ("$schema", "wrong"),
            ("version", "01.0.0"),
            ("version", 1),
            ("description", ""),
            ("skills", "./skills/"),
        ):
            with self.subTest(key=key, value=value):
                self.write("plugin.json", {**original, key: value})
                with self.assertRaises(ValueError):
                    validate(self.root)

    def test_invalid_marketplace(self) -> None:
        original = (self.root / ".agents/plugins/marketplace.json").read_text()
        for relative in (".", "../", "./../", "./missing", "./.agents/plugins", str(self.root)):
            with self.subTest(path=relative):
                market = json.loads(original)
                market["plugins"][0]["source"]["path"] = relative
                self.write(".agents/plugins/marketplace.json", market)
                with self.assertRaises(ValueError):
                    validate(self.root)
        for key, value in (("name", "wrong-plugin"), ("policy", {}), ("category", None)):
            with self.subTest(key=key):
                market = json.loads(original)
                market["plugins"][0][key] = value
                self.write(".agents/plugins/marketplace.json", market)
                with self.assertRaises(ValueError):
                    validate(self.root)

    def test_missing_skills(self) -> None:
        shutil.rmtree(self.root / "skills")
        with self.assertRaisesRegex(ValueError, "skills/"):
            validate(self.root)

    def test_duplicate_manifest(self) -> None:
        overlay = self.root / ".codex-plugin/plugin.json"
        overlay.parent.mkdir()
        overlay.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected package component"):
            validate(self.root)

    def test_skill_symlink_escape(self) -> None:
        (self.root / "skills/escape").symlink_to(
            REPO_ROOT / "skills/tech-post-maker", target_is_directory=True
        )
        with self.assertRaisesRegex(ValueError, "escapes plugin root"):
            validate(self.root)


if __name__ == "__main__":
    unittest.main()
