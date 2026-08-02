#!/usr/bin/env python3
"""Tests for the Codex Insights hook installer."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("install_hooks.py")
SKILL_ROOT = Path(__file__).resolve().parents[1]


def run_installer(
    project: Path, codex: Path, claude: Path, *args: str
) -> subprocess.CompletedProcess[str]:
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
            "--allow-custom-hooks-path",
            *args,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def insight_entries(config: dict, event: str) -> list[dict]:
    return [
        entry
        for entry in config.get("hooks", {}).get(event, [])
        if "CODEX_INSIGHTS_HOOK_ID=codex-insights:" in json.dumps(entry)
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
            self.assertEqual(len(insight_entries(codex_config, "PreToolUse")), 1)
            self.assertEqual(len(insight_entries(claude_config, "Stop")), 1)
            command = insight_entries(codex_config, "PreToolUse")[0]["hooks"][0]["command"]
            self.assertIn("CODEX_INSIGHTS_SCOPE_ROOT=", command)
            self.assertIn("observe.sh pre", command)

    def test_custom_hook_path_requires_explicit_allow_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--project-root",
                    str(root),
                    "--skill-root",
                    str(SKILL_ROOT),
                    "--target",
                    "codex",
                    "--codex-hooks-path",
                    str(codex),
                    "--apply",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--allow-custom-hooks-path", result.stderr)
            self.assertFalse(codex.exists())

    def test_external_skill_root_requires_trust_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external_skill = root / "external-skill"
            hook = external_skill / "hooks" / "observe.sh"
            hook.parent.mkdir(parents=True)
            hook.write_text("#!/bin/sh\n", encoding="utf-8")
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--project-root",
                    str(root),
                    "--skill-root",
                    str(external_skill),
                    "--codex-hooks-path",
                    str(codex),
                    "--claude-hooks-path",
                    str(claude),
                    "--allow-custom-hooks-path",
                    "--apply",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--trust-skill-root", result.stderr)

    def test_global_scope_omits_project_scope_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            result = run_installer(
                root, codex, claude, "--scope", "global", "--target", "codex", "--apply"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            codex_config = load(codex)
            command = insight_entries(codex_config, "PreToolUse")[0]["hooks"][0]["command"]
            self.assertIn("CODEX_INSIGHTS_SCOPE=global", command)
            self.assertIn("CODEX_INSIGHTS_HOOK_ID=codex-insights:pre:global", command)
            self.assertNotIn("CODEX_INSIGHTS_SCOPE_ROOT=", command)

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
            for event in (
                "UserPromptSubmit",
                "PreToolUse",
                "PostToolUse",
                "Stop",
                "PreCompact",
                "PostCompact",
            ):
                self.assertEqual(len(insight_entries(codex_config, event)), 1)
                self.assertEqual(len(insight_entries(claude_config, event)), 1)

    def test_apply_replaces_and_uninstall_removes_legacy_registration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apply_hooks = root / "apply-hooks.json"
            uninstall_hooks = root / "uninstall-hooks.json"
            claude = root / "claude-hooks.json"
            legacy_entry = {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            "env SESSION_LEARNING_HOOK_ID=session-learning:pre:global "
                            "SESSION_LEARNING_SCOPE=global /bin/bash /tmp/session-learning/hooks/observe.sh pre"
                        ),
                    }
                ],
            }
            legacy_config = {"hooks": {"PreToolUse": [legacy_entry]}}
            apply_hooks.write_text(json.dumps(legacy_config), encoding="utf-8")
            uninstall_hooks.write_text(json.dumps(legacy_config), encoding="utf-8")

            apply_result = run_installer(
                root, apply_hooks, claude, "--scope", "global", "--target", "codex", "--apply"
            )
            uninstall_result = run_installer(
                root,
                uninstall_hooks,
                claude,
                "--scope",
                "global",
                "--target",
                "codex",
                "--uninstall",
                "--apply",
            )

            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            self.assertEqual(uninstall_result.returncode, 0, uninstall_result.stderr)
            self.assertEqual(len(insight_entries(load(apply_hooks), "PreToolUse")), 1)
            self.assertNotIn("session-learning", apply_hooks.read_text(encoding="utf-8"))
            self.assertEqual(load(uninstall_hooks)["hooks"]["PreToolUse"], [])

    def test_legacy_migration_covers_scopes_targets_and_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for scope in ("project", "global"):
                for target in ("codex", "claude"):
                    for action in ("apply", "uninstall"):
                        with self.subTest(scope=scope, target=target, action=action):
                            case_root = root / f"{scope}-{target}-{action}"
                            case_root.mkdir()
                            pid = (
                                "global"
                                if scope == "global"
                                else hashlib.sha256(str(case_root.resolve()).encode()).hexdigest()[
                                    :12
                                ]
                            )
                            codex = case_root / "codex-hooks.json"
                            claude = case_root / "claude-hooks.json"
                            config_path = codex if target == "codex" else claude
                            command = (
                                "env SESSION_LEARNING_HOOK_ID=session-learning:pre:"
                                f"{pid} /bin/bash /tmp/session-learning/hooks/observe.sh pre"
                            )
                            entry = {
                                "matcher": "*",
                                "hooks": [{"type": "command", "command": command}],
                            }
                            if target == "claude":
                                entry = {
                                    "id": f"session-learning:pre:{pid}",
                                    "matcher": "*",
                                    "hooks": [{"type": "command", "command": "echo legacy"}],
                                }
                            config_path.write_text(
                                json.dumps({"hooks": {"PreToolUse": [entry]}}),
                                encoding="utf-8",
                            )
                            args = ["--target", target, "--apply"]
                            if scope == "global":
                                args.extend(("--scope", "global"))
                            if action == "uninstall":
                                args.append("--uninstall")

                            result = run_installer(case_root, codex, claude, *args)

                            self.assertEqual(result.returncode, 0, result.stderr)
                            config = load(config_path)
                            self.assertNotIn("session-learning", json.dumps(config))
                            expected = 1 if action == "apply" else 0
                            self.assertEqual(len(insight_entries(config, "PreToolUse")), expected)

    def test_apply_then_uninstall_preserves_unrelated_commands_in_mixed_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for target in ("codex", "claude"):
                with self.subTest(target=target):
                    case_root = root / target
                    case_root.mkdir()
                    codex = case_root / "codex-hooks.json"
                    claude = case_root / "claude-hooks.json"
                    config_path = codex if target == "codex" else claude
                    entry = {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "echo keep"},
                            {
                                "type": "command",
                                "command": (
                                    "env CODEX_INSIGHTS_HOOK_ID=codex-insights:pre:global "
                                    "/bin/bash /tmp/codex-insights/hooks/observe.sh pre"
                                ),
                            },
                            {
                                "type": "command",
                                "command": (
                                    "env SESSION_LEARNING_HOOK_ID=session-learning:pre:global "
                                    "/bin/bash /tmp/session-learning/hooks/observe.sh pre"
                                ),
                            },
                        ],
                    }
                    if target == "claude":
                        entry["id"] = "session-learning:pre:global"
                    config_path.write_text(
                        json.dumps({"hooks": {"PreToolUse": [entry]}}),
                        encoding="utf-8",
                    )

                    apply_result = run_installer(
                        case_root,
                        codex,
                        claude,
                        "--scope",
                        "global",
                        "--target",
                        target,
                        "--apply",
                    )
                    self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
                    applied_entries = load(config_path)["hooks"]["PreToolUse"]
                    self.assertEqual(
                        applied_entries[0]["hooks"], [{"type": "command", "command": "echo keep"}]
                    )
                    self.assertNotIn("id", applied_entries[0])

                    uninstall_result = run_installer(
                        case_root,
                        codex,
                        claude,
                        "--scope",
                        "global",
                        "--target",
                        target,
                        "--uninstall",
                        "--apply",
                    )
                    self.assertEqual(uninstall_result.returncode, 0, uninstall_result.stderr)
                    remaining = load(config_path)["hooks"]["PreToolUse"]
                    self.assertEqual(
                        remaining,
                        [{"matcher": "*", "hooks": [{"type": "command", "command": "echo keep"}]}],
                    )

    def test_backups_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            codex.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
            first = run_installer(root, codex, claude, "--target", "codex", "--apply")
            second = run_installer(
                root, codex, claude, "--target", "codex", "--uninstall", "--apply"
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            backups = sorted(root.glob("codex-hooks.json.bak-*"))
            self.assertEqual(len(backups), 2)
            self.assertEqual(len({backup.name for backup in backups}), 2)

    def test_backup_preserves_restrictive_source_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            codex.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
            codex.chmod(0o600)
            previous_umask = os.umask(0o022)
            try:
                result = run_installer(root, codex, claude, "--target", "codex", "--apply")
            finally:
                os.umask(previous_umask)
            self.assertEqual(result.returncode, 0, result.stderr)
            backup = next(root.glob("codex-hooks.json.bak-*"))
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_hook_config_rejects_target_and_parent_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude = root / "claude-hooks.json"
            real_hooks = root / "real-hooks.json"
            real_hooks.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
            direct_link = root / "codex-hooks.json"
            direct_link.symlink_to(real_hooks)
            real_parent = root / "real-parent"
            real_parent.mkdir()
            linked_parent = root / "linked-parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)

            for codex in (direct_link, linked_parent / "codex-hooks.json"):
                with self.subTest(path=codex):
                    result = run_installer(root, codex, claude, "--target", "codex", "--apply")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("symlink is not allowed", result.stderr)
            self.assertEqual(load(real_hooks), {"hooks": {}})
            self.assertFalse((real_parent / "codex-hooks.json").exists())

    def test_uninstall_preserves_unrelated_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            codex.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [
                                {
                                    "matcher": "Bash",
                                    "hooks": [{"type": "command", "command": "echo keep"}],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            apply_result = run_installer(root, codex, claude, "--apply")
            uninstall_result = run_installer(root, codex, claude, "--uninstall", "--apply")
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            self.assertEqual(uninstall_result.returncode, 0, uninstall_result.stderr)
            codex_config = load(codex)
            self.assertEqual(
                codex_config["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "echo keep"
            )
            self.assertEqual(insight_entries(codex_config, "PreToolUse"), [])

    def test_uninstall_does_not_create_missing_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            codex.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
            result = run_installer(
                root, codex, claude, "--target", "codex", "--uninstall", "--apply"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(load(codex), {"hooks": {}})

    def test_global_uninstall_preserves_project_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex-hooks.json"
            claude = root / "claude-hooks.json"
            project_result = run_installer(root, codex, claude, "--target", "codex", "--apply")
            global_result = run_installer(
                root, codex, claude, "--scope", "global", "--target", "codex", "--apply"
            )
            uninstall_global = run_installer(
                root,
                codex,
                claude,
                "--scope",
                "global",
                "--target",
                "codex",
                "--uninstall",
                "--apply",
            )
            self.assertEqual(project_result.returncode, 0, project_result.stderr)
            self.assertEqual(global_result.returncode, 0, global_result.stderr)
            self.assertEqual(uninstall_global.returncode, 0, uninstall_global.stderr)
            codex_config = load(codex)
            commands = json.dumps(codex_config)
            self.assertIn("CODEX_INSIGHTS_SCOPE=project", commands)
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
            apply_result = run_installer(
                root, codex, claude, "--scope", "global", "--target", "codex", "--apply"
            )
            status_result = run_installer(
                root, codex, claude, "--scope", "global", "--target", "codex", "--status"
            )
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
                "env CODEX_INSIGHTS_HOOK_ID=codex-insights:pre:global "
                "CODEX_INSIGHTS_SCOPE=global /bin/bash /tmp/stale/observe.sh pre"
            )
            codex.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [
                                {
                                    "matcher": "*",
                                    "hooks": [{"type": "command", "command": stale_command}],
                                },
                                {
                                    "matcher": "*",
                                    "hooks": [{"type": "command", "command": stale_command}],
                                },
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            result = run_installer(
                root, codex, claude, "--scope", "global", "--target", "codex", "--status"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            status = payload["results"][0]
            self.assertIn("PreToolUse", status["duplicate_events"])
            self.assertEqual(status["duplicate_count"], 1)
            self.assertEqual(len(status["stale_paths"]), 2)


if __name__ == "__main__":
    unittest.main()
