#!/usr/bin/env python3
"""Fixture tests for the session learning observer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("learning_observer.py")


class LearningObserverTests(unittest.TestCase):
    def run_observer(
        self,
        root: Path,
        payload: str,
        phase: str = "post",
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["SESSION_LEARNING_PROJECT_DIR"] = str(root)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--phase", phase],
            input=payload,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_redacts_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "session_id": "s1",
                "cwd": str(root),
                "tool_name": "Bash",
                "tool_input": {"command": "curl -H 'Authorization: Bearer abcdefghijklmnop'"},
                "tool_response": "api_key=sk-1234567890abcdef",
            }
            result = self.run_observer(root, json.dumps(payload))
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (root / ".omx" / "learning" / "observations.jsonl").read_text()
            self.assertIn("[REDACTED]", text)
            self.assertNotIn("abcdefghijklmnop", text)
            self.assertNotIn("sk-1234567890abcdef", text)

    def test_malformed_json_writes_parse_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_observer(root, "{not-json")
            self.assertEqual(result.returncode, 0, result.stderr)
            row = json.loads((root / ".omx" / "learning" / "observations.jsonl").read_text())
            self.assertEqual(row["outcome_signal"], "parse_error")

    def test_stop_writes_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"session_id": "s2", "cwd": str(root), "tool_name": "Stop"}
            result = self.run_observer(root, json.dumps(payload), phase="stop")
            self.assertEqual(result.returncode, 0, result.stderr)
            candidates = list((root / ".omx" / "learning" / "candidates").glob("*.md"))
            self.assertEqual(len(candidates), 1)
            text = candidates[0].read_text()
            self.assertIn("Session Learning Candidate", text)
            self.assertIn("promotion_scope: project", text)
            self.assertIn("recommended_target: AGENTS.md", text)
            self.assertIn("source_projects:", text)

    def test_scope_root_skips_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            payload = {"session_id": "s3", "cwd": str(outside), "tool_name": "Bash"}
            result = self.run_observer(
                root,
                json.dumps(payload),
                extra_env={"SESSION_LEARNING_SCOPE_ROOT": str(root), "SESSION_LEARNING_PROJECT_DIR": ""},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / ".omx" / "learning" / "observations.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
