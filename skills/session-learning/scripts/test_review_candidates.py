#!/usr/bin/env python3
"""Tests for the session-learning candidate review helper."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("review_candidates.py")


def write_candidate(root: Path, name: str, body: str, frontmatter: str = "") -> Path:
    candidate_dir = root / ".omx" / "learning" / "candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    content = frontmatter or "---\nstatus: candidate\npromotion_scope: project\n---\n"
    path = candidate_dir / name
    path.write_text(content + "\n" + body, encoding="utf-8")
    return path


def run_review(root: Path, *extra_args: str, output_format: str = "json") -> dict | str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--roots", str(root), "--format", output_format, *extra_args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    if output_format == "markdown":
        return result.stdout
    return json.loads(result.stdout)


class ReviewCandidatesTests(unittest.TestCase):
    def test_routes_candidates_by_promotion_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_candidate(root, "project.md", "Remember this project route and test command.")
            write_candidate(root, "workspace.md", "Preserve child repo autonomy across this workspace.")
            write_candidate(root, "global.md", "This should apply to all projects as global policy.")
            write_candidate(root, "skill.md", "This is a reusable workflow with repeatable steps.")
            write_candidate(root, "subagent.md", "This is a bounded role for repeated CI failure triage.")
            write_candidate(root, "archive.md", "This is a duplicate candidate and should archive.")
            payload = run_review(root)
            scopes = {Path(item["path"]).name: item["promotion_scope"] for item in payload["candidates"]}
            self.assertEqual(scopes["project.md"], "project")
            self.assertEqual(scopes["workspace.md"], "workspace")
            self.assertEqual(scopes["global.md"], "user-global")
            self.assertEqual(scopes["skill.md"], "skill")
            self.assertEqual(scopes["subagent.md"], "subagent")
            self.assertEqual(scopes["archive.md"], "archive")

    def test_honors_explicit_non_project_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_candidate(
                root,
                "explicit.md",
                "Short note.",
                frontmatter="---\nstatus: candidate\npromotion_scope: user-global\nrecommended_target: ~/.codex/AGENTS.md\n---\n",
            )
            payload = run_review(root)
            self.assertIsInstance(payload, dict)
            self.assertEqual(payload["candidates"][0]["promotion_scope"], "user-global")
            self.assertEqual(payload["candidates"][0]["target"], "~/.codex/AGENTS.md")

    def test_since_days_filters_old_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_path = write_candidate(root, "old.md", "Old project-specific learning.")
            new_path = write_candidate(root, "new.md", "New workspace child repo boundary learning.")
            old_time = 1_600_000_000
            os.utime(old_path, (old_time, old_time))
            payload = run_review(root, "--since-days", "1")
            self.assertIsInstance(payload, dict)
            names = {Path(item["path"]).name for item in payload["candidates"]}
            self.assertEqual(names, {new_path.name})

    def test_empty_results_render_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = run_review(root)
            self.assertIsInstance(payload, dict)
            self.assertEqual(payload["candidates"], [])

            markdown = run_review(root, output_format="markdown")
            self.assertIsInstance(markdown, str)
            self.assertIn("Candidates found: 0", markdown)
            self.assertIn("No candidates found.", markdown)


if __name__ == "__main__":
    unittest.main()
