#!/usr/bin/env python3
"""Fixture tests for the session learning observer."""

from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("learning_observer.py")
SPEC = importlib.util.spec_from_file_location("learning_observer", SCRIPT)
assert SPEC and SPEC.loader
learning_observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(learning_observer)


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

    def test_dry_run_prints_observation_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = os.environ.copy()
            env["SESSION_LEARNING_PROJECT_DIR"] = str(root)
            payload = {"session_id": "s-dry", "cwd": str(root), "tool_name": "Bash"}
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--phase", "post", "--dry-run"],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            row = json.loads(result.stdout)
            self.assertEqual(row["session_id"], "s-dry")
            self.assertFalse((root / ".omx" / "learning" / "observations.jsonl").exists())
            self.assertEqual(list((root / ".omx" / "learning" / "candidates").glob("*.md")), [])

    def test_appends_observations_without_overwriting_existing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = {"session_id": "existing", "outcome_signal": "observed"}
            observation_path = root / ".omx" / "learning" / "observations.jsonl"
            observation_path.parent.mkdir(parents=True, exist_ok=True)
            observation_path.write_text(json.dumps(existing) + "\n", encoding="utf-8")

            payload = {"session_id": "new", "cwd": str(root), "tool_name": "Bash"}
            result = self.run_observer(root, json.dumps(payload))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [json.loads(line) for line in observation_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["session_id"] for row in rows], ["existing", "new"])

    def test_stop_candidate_paths_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = learning_observer.learning_dirs(root)
            first = learning_observer.unique_candidate_path(paths["candidates"], "same-session")
            first.write_text("existing", encoding="utf-8")
            second = learning_observer.unique_candidate_path(paths["candidates"], "same-session")
            self.assertNotEqual(first, second)

    def test_observation_includes_root_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"session_id": "s-root", "cwd": str(root), "tool_name": "Bash"}
            result = self.run_observer(root, json.dumps(payload))
            self.assertEqual(result.returncode, 0, result.stderr)
            row = json.loads((root / ".omx" / "learning" / "observations.jsonl").read_text())
            self.assertEqual(row["root_source"], "env")

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

    def test_env_project_dir_mismatch_falls_back_to_event_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            event_root = Path(tmp)
            env_root = Path(other)
            payload = {"session_id": "s-env", "cwd": str(event_root), "tool_name": "Bash"}
            result = self.run_observer(env_root, json.dumps(payload), extra_env={"SESSION_LEARNING_PROJECT_DIR": str(env_root)})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((env_root / ".omx" / "learning" / "observations.jsonl").exists())
            row = json.loads((event_root / ".omx" / "learning" / "observations.jsonl").read_text())
            self.assertEqual(row["root_source"], "cwd-fallback")
            self.assertIn("env_project_dir_rejected", row["root_warning"])


if __name__ == "__main__":
    unittest.main()
