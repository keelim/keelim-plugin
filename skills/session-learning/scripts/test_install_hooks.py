#!/usr/bin/env python3
"""Tests for the session-learning hook installer."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("install_hooks.py")
SKILL_ROOT = Path(__file__).resolve().parents[1]


def run_installer(project: Path, codex: Path, claude: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(project),
            "--skill-root",
            str(SKILL_ROOT),
            "--codex-hooks-path",
            str(codex),
            "--claude-hooks-path",
            str(claude),
            *args,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def session_entries(config: dict, event: str) -> list[dict]:
    return [
        entry
        for entry in config.get("hooks", {}).get(event, [])
        if "SESSION_LEARNING_HOOK_ID=session-learning:" in json.dumps(entry)
    ]


class InstallHooksTests(unittest.TestCase):
    def test_dry_run_does_not_write_configs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            result = run_installer(root, codex, claude)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"dry_run": true', result.stdout)
            self.assertFalse(codex.exists())
            self.assertFalse(claude.exists())

    def test_apply_adds_codex_and_claude_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            result = run_installer(root, codex, claude, "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)
            codex_config = load(codex)
            claude_config = load(claude)
            self.assertEqual(len(session_entries(codex_config, "PreToolUse")), 1)
            self.assertEqual(len(session_entries(claude_config, "Stop")), 1)
            command = session_entries(codex_config, "PreToolUse")[0]["hooks"][0]["command"]
            self.assertIn("SESSION_LEARNING_SCOPE_ROOT=", command)
            self.assertIn("observe.sh pre", command)

    def test_global_scope_omits_project_scope_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            result = run_installer(root, codex, claude, "--scope", "global", "--target", "codex", "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)
            codex_config = load(codex)
            command = session_entries(codex_config, "PreToolUse")[0]["hooks"][0]["command"]
            self.assertIn("SESSION_LEARNING_SCOPE=global", command)
            self.assertIn("SESSION_LEARNING_HOOK_ID=session-learning:pre:global", command)
            self.assertNotIn("SESSION_LEARNING_SCOPE_ROOT=", command)

    def test_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            first = run_installer(root, codex, claude, "--apply")
            second = run_installer(root, codex, claude, "--apply")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            codex_config = load(codex)
            claude_config = load(claude)
            for event in ("UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "PreCompact", "PostCompact"):
                self.assertEqual(len(session_entries(codex_config, event)), 1)
                self.assertEqual(len(session_entries(claude_config, event)), 1)

    def test_uninstall_preserves_unrelated_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            codex.write_text(
                json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo keep"}]}]}}),
                encoding="utf-8",
            )
            apply_result = run_installer(root, codex, claude, "--apply")
            uninstall_result = run_installer(root, codex, claude, "--uninstall", "--apply")
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            self.assertEqual(uninstall_result.returncode, 0, uninstall_result.stderr)
            codex_config = load(codex)
            self.assertEqual(codex_config["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "echo keep")
            self.assertEqual(session_entries(codex_config, "PreToolUse"), [])

    def test_uninstall_does_not_create_missing_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            codex.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
            result = run_installer(root, codex, claude, "--target", "codex", "--uninstall", "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(load(codex), {"hooks": {}})

    def test_global_uninstall_preserves_project_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            project_result = run_installer(root, codex, claude, "--target", "codex", "--apply")
            global_result = run_installer(root, codex, claude, "--scope", "global", "--target", "codex", "--apply")
            uninstall_global = run_installer(root, codex, claude, "--scope", "global", "--target", "codex", "--uninstall", "--apply")
            self.assertEqual(project_result.returncode, 0, project_result.stderr)
            self.assertEqual(global_result.returncode, 0, global_result.stderr)
            self.assertEqual(uninstall_global.returncode, 0, uninstall_global.stderr)
            codex_config = load(codex)
            commands = json.dumps(codex_config)
            self.assertIn("SESSION_LEARNING_SCOPE=project", commands)
            self.assertNotIn("session-learning:pre:global", commands)

    def test_status_reports_missing_registration_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            result = run_installer(root, codex, claude, "--target", "codex", "--status")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "status")
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["results"][0]["registered_events"], 0)
            self.assertIn("PreToolUse", payload["results"][0]["missing_events"])
            self.assertFalse(codex.exists())

    def test_status_reports_global_registration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            apply_result = run_installer(root, codex, claude, "--scope", "global", "--target", "codex", "--apply")
            status_result = run_installer(root, codex, claude, "--scope", "global", "--target", "codex", "--status")
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            self.assertEqual(status_result.returncode, 0, status_result.stderr)
            payload = json.loads(status_result.stdout)
            self.assertEqual(payload["project_id"], "global")
            self.assertEqual(payload["results"][0]["registered_events"], 6)
            self.assertEqual(payload["results"][0]["missing_events"], [])

    def test_status_reports_duplicate_and_stale_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            stale_command = (
                "env SESSION_LEARNING_HOOK_ID=session-learning:pre:global "
                "SESSION_LEARNING_SCOPE=global /bin/bash /tmp/stale/observe.sh pre"
            )
            codex.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [
                                {"matcher": "*", "hooks": [{"type": "command", "command": stale_command}]},
                                {"matcher": "*", "hooks": [{"type": "command", "command": stale_command}]},
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            result = run_installer(root, codex, claude, "--scope", "global", "--target", "codex", "--status")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            status = payload["results"][0]
            self.assertIn("PreToolUse", status["duplicate_events"])
            self.assertEqual(status["duplicate_count"], 1)
            self.assertEqual(len(status["stale_paths"]), 2)


if __name__ == "__main__":
    unittest.main()
