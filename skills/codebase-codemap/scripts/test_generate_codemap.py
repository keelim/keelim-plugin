#!/usr/bin/env python3
"""Tests for the source-led codemap generator."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import generate_codemap


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class GenerateCodemapTests(unittest.TestCase):
    def test_generate_markdown_finds_manifests_tests_and_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-repo"
            write(root / "AGENTS.md", "# Instructions\n")
            write(root / "README.md", "# Demo\n")
            write(root / "package.json", '{"scripts":{"test":"node test.js"}}\n')
            write(root / "src" / "app.py", "class Service:\n    pass\n\ndef main():\n    pass\n")
            write(root / "tests" / "test_app.py", "def test_main():\n    pass\n")

            args = generate_codemap.parse_args([str(root), "--stdout", "--full-scan", "--allow-outside-root"])
            markdown = generate_codemap.generate_markdown(args)

            self.assertIn("# Agent Codemap", markdown)
            self.assertIn("- Repository: `demo-repo`", markdown)
            self.assertIn("AGENTS.md", markdown)
            self.assertIn("package.json", markdown)
            self.assertIn("tests/test_app.py", markdown)
            self.assertIn("src/app.py", markdown)
            self.assertIn("Service", markdown)
            self.assertIn("main", markdown)

    def test_iter_repo_files_skips_private_hidden_and_dependency_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / ".github" / "workflows" / "ci.yml", "name: ci\n")
            write(root / ".codex" / "sessions" / "one.jsonl", "{}\n")
            write(root / ".claude" / "settings.json", "{}\n")
            write(root / "node_modules" / "pkg" / "index.js", "module.exports = {}\n")
            write(root / "src" / "app.py", "def app():\n    pass\n")
            outside = Path(tmp) / "outside-secret.txt"
            outside.write_text("secret\n", encoding="utf-8")
            (root / "linked-secret.txt").symlink_to(outside)

            files = {path.relative_to(root).as_posix() for path in generate_codemap.iter_repo_files(root)}

            self.assertIn(".github/workflows/ci.yml", files)
            self.assertIn("src/app.py", files)
            self.assertNotIn(".codex/sessions/one.jsonl", files)
            self.assertNotIn(".claude/settings.json", files)
            self.assertNotIn("node_modules/pkg/index.js", files)
            self.assertNotIn("linked-secret.txt", files)

    def test_default_output_writes_project_named_codemap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo repo"
            write(root / "README.md", "# Demo\n")
            exit_code = generate_codemap.main(
                [str(root), "--project-name", "Demo Repo", "--full-scan", "--allow-outside-root"]
            )

            output = root / "docs" / "CODEMAPS" / "Demo-Repo.md"
            self.assertEqual(exit_code, 0)
            self.assertTrue(output.is_file())
            output_text = output.read_text(encoding="utf-8")
            self.assertIn("# Agent Codemap", output_text)
            self.assertIn("- Repository: `demo repo`", output_text)

    def test_output_dir_writes_project_named_codemap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo"
            write(root / "README.md", "# Demo\n")
            exit_code = generate_codemap.main([str(root), "--output-dir", "maps", "--full-scan", "--allow-outside-root"])

            output = root / "maps" / "demo.md"
            self.assertEqual(exit_code, 0)
            self.assertTrue(output.is_file())

    def test_outside_repo_scan_requires_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "outside"
            write(root / "README.md", "# Outside\n")
            with self.assertRaises(SystemExit):
                generate_codemap.main([str(root), "--stdout"])

    def test_absolute_output_requires_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo"
            write(root / "README.md", "# Demo\n")
            output = Path(tmp) / "outside.md"
            with self.assertRaises(SystemExit):
                generate_codemap.main(
                    [str(root), "--output", str(output), "--allow-outside-root", "--full-scan"]
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
