#!/usr/bin/env python3
"""Fixture tests for the Codex Insights observer."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).with_name("insight_observer.py")
SPEC = importlib.util.spec_from_file_location("insight_observer", SCRIPT)
assert SPEC and SPEC.loader
insight_observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(insight_observer)


class InsightObserverTests(unittest.TestCase):
    def assert_policy_failure(self, result: subprocess.CompletedProcess[str], message: str) -> None:
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"UnsafeStoragePath: {message}", result.stderr)

    def run_observer(
        self,
        root: Path,
        payload: str,
        phase: str = "post",
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["CODEX_INSIGHTS_PROJECT_DIR"] = str(root)
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

    def init_git(self, root: Path) -> None:
        result = subprocess.run(
            ["git", "init", "--quiet"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def add_gitlink(self, root: Path, path: str) -> None:
        object_result = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=root,
            input="gitlink",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(object_result.returncode, 0, object_result.stderr)
        indexed = subprocess.run(
            [
                "git",
                "update-index",
                "--add",
                "--cacheinfo",
                f"160000,{object_result.stdout.strip()},{path}",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(indexed.returncode, 0, indexed.stderr)

    def test_never_persists_free_form_payload_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample_text = "login with credential fixture"
            secret_dir = root / sample_text
            secret_dir.mkdir()
            payload = {
                "session_id": f"session-{sample_text}",
                "tool_use_id": f"call-{sample_text}",
                "cwd": str(secret_dir),
                "tool_name": sample_text,
                "tool_input": {
                    "command": sample_text,
                    "prompt": f"Please run {sample_text}",
                },
                "tool_response": f"authentication failed for {sample_text}",
                "error": f"error: {sample_text}",
            }
            result = self.run_observer(
                root,
                json.dumps(payload),
                phase=sample_text,
                extra_env={"CODEX_INSIGHTS_SOURCE": sample_text},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (root / ".omx" / "learning" / "observations.jsonl").read_text()
            row = json.loads(text)
            self.assertEqual(row["content_policy"], "metadata-only")
            self.assertEqual(row["phase"], "other")
            self.assertEqual(row["source"], "configured")
            self.assertEqual(row["cwd"], "inside-project")
            self.assertTrue(row["tool"].startswith("tool-name-"))
            self.assertEqual(row["outcome_signal"], "error-signal")
            self.assertFalse({"input_preview", "output_preview", "prompt", "error"} & row.keys())
            self.assertNotIn(sample_text, text)

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
            self.assertIn("Codex Insights Candidate", text)
            self.assertIn("promotion_scope: project", text)
            self.assertIn("recommended_target: AGENTS.md", text)
            self.assertIn("source_projects:", text)

    def test_storage_uses_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"session_id": "private", "cwd": str(root), "tool_name": "Stop"}
            result = self.run_observer(root, json.dumps(payload), phase="stop")
            self.assertEqual(result.returncode, 0, result.stderr)
            base = root / ".omx" / "learning"
            for directory in (
                root / ".omx",
                base,
                base / "candidates",
                base / "promoted",
                base / "archive",
            ):
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            observation_path = base / "observations.jsonl"
            candidate_path = next((base / "candidates").glob("*.md"))
            self.assertEqual(stat.S_IMODE(observation_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(candidate_path.stat().st_mode), 0o600)

    def test_storage_preserves_existing_omx_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            omx = root / ".omx"
            omx.mkdir(mode=0o755)
            omx.chmod(0o755)
            payload = {"session_id": "private", "cwd": str(root), "tool_name": "Bash"}

            result = self.run_observer(root, json.dumps(payload), phase="post")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(stat.S_IMODE(omx.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE((omx / "learning").stat().st_mode), 0o700)

    def test_ids_and_paths_are_anonymized_stably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "session_id": "raw-session-id",
                "tool_use_id": "raw-tool-id",
                "cwd": str(root),
                "tool_name": "Bash",
            }
            for _ in range(2):
                result = self.run_observer(root, json.dumps(payload))
                self.assertEqual(result.returncode, 0, result.stderr)
            text = (root / ".omx" / "learning" / "observations.jsonl").read_text()
            rows = [json.loads(line) for line in text.splitlines()]
            self.assertEqual(rows[0]["session_id"], rows[1]["session_id"])
            self.assertEqual(rows[0]["tool_use_id"], rows[1]["tool_use_id"])
            self.assertEqual(rows[0]["cwd"], "project-root")
            self.assertEqual(rows[0]["project_root"], "[project-root]")
            self.assertNotIn("raw-session-id", text)
            self.assertNotIn("raw-tool-id", text)
            self.assertNotIn(str(root), text)

    def test_rejects_symlinked_storage_components_and_observation_file(self) -> None:
        for component in (".omx", ".omx/learning"):
            with (
                self.subTest(component=component),
                tempfile.TemporaryDirectory() as tmp,
                tempfile.TemporaryDirectory() as target,
            ):
                root = Path(tmp)
                link = root / component
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(target, target_is_directory=True)
                payload = {"session_id": "symlink", "cwd": str(root), "tool_name": "Bash"}
                result = self.run_observer(root, json.dumps(payload))
                self.assertNotEqual(result.returncode, 0)

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as target:
            root = Path(tmp)
            paths = insight_observer.learning_dirs(root)
            target_file = Path(target) / "outside.jsonl"
            target_file.write_text("unchanged", encoding="utf-8")
            paths["observations"].symlink_to(target_file)
            payload = {"session_id": "symlink", "cwd": str(root), "tool_name": "Bash"}
            result = self.run_observer(root, json.dumps(payload))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target_file.read_text(encoding="utf-8"), "unchanged")

    def test_parent_symlink_swap_cannot_redirect_observation_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as target:
            root = Path(tmp)
            outside = Path(target)
            paths = insight_observer.learning_dirs(root)
            learning = paths["base"]
            parked = learning.with_name("learning-before-swap")
            real_open = os.open
            swapped = False

            def swap_parent_before_file_open(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                nonlocal swapped
                if not swapped and Path(os.fsdecode(path)).name == "observations.jsonl":
                    learning.rename(parked)
                    learning.symlink_to(outside, target_is_directory=True)
                    swapped = True
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(insight_observer.os, "open", swap_parent_before_file_open):
                insight_observer.append_jsonl(paths["observations"], {"session_id": "s"}, root)

            self.assertTrue(swapped)
            self.assertTrue((parked / "observations.jsonl").is_file())
            self.assertFalse((outside / "observations.jsonl").exists())

    def test_git_tracked_observations_are_rejected_even_when_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            paths = insight_observer.learning_dirs(root)
            observations = paths["observations"]
            observations.write_text("tracked\n", encoding="utf-8")
            (root / ".gitignore").write_text(".omx/\n", encoding="utf-8")
            added = subprocess.run(
                ["git", "add", "--force", ".omx/learning/observations.jsonl"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(added.returncode, 0, added.stderr)

            with self.assertRaises(insight_observer.UnsafeStoragePath):
                insight_observer.append_jsonl(observations, {"session_id": "s"}, root)

            self.assertEqual(observations.read_text(encoding="utf-8"), "tracked\n")

    def test_git_tracked_case_alias_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            paths = insight_observer.learning_dirs(root)
            observations = paths["observations"]
            observations.write_text("tracked-alias\n", encoding="utf-8")
            (root / ".gitignore").write_text(".omx/\n", encoding="utf-8")
            blob = subprocess.run(
                ["git", "hash-object", "-w", ".omx/learning/observations.jsonl"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(blob.returncode, 0, blob.stderr)
            indexed = subprocess.run(
                [
                    "git",
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"100644,{blob.stdout.strip()},.OMX/LEARNING/OBSERVATIONS.JSONL",
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(indexed.returncode, 0, indexed.stderr)

            with self.assertRaises(insight_observer.UnsafeStoragePath):
                insight_observer.append_jsonl(observations, {"session_id": "s"}, root)

            self.assertEqual(observations.read_text(encoding="utf-8"), "tracked-alias\n")

    def test_attacker_path_fake_git_cannot_allow_tracked_observations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            paths = insight_observer.learning_dirs(root)
            observations = paths["observations"]
            observations.write_text("tracked\n", encoding="utf-8")
            (root / ".gitignore").write_text(".omx/\n", encoding="utf-8")
            added = subprocess.run(
                ["git", "add", "--force", ".omx/learning/observations.jsonl"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            fake_bin = root / "attacker-bin"
            fake_bin.mkdir()
            fake_git = fake_bin / "git"
            fake_git.write_text(
                """#!/bin/sh
if [ "$1" = "-c" ]; then shift 2; fi
case "$1" in
  rev-parse) pwd; exit 0 ;;
  check-ignore) exit 0 ;;
  ls-files)
    case " $* " in
      *" --stage "*) exit 0 ;;
      *) exit 1 ;;
    esac ;;
esac
exit 0
""",
                encoding="utf-8",
            )
            fake_git.chmod(0o755)
            payload = {"session_id": "path-poison", "cwd": str(root), "tool_name": "Bash"}

            result = self.run_observer(
                root,
                json.dumps(payload),
                extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
            )

            self.assert_policy_failure(result, "Git-tracked storage path is not allowed")
            self.assertEqual(observations.read_text(encoding="utf-8"), "tracked\n")

    def test_git_trace_cannot_mutate_tracked_observations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            paths = insight_observer.learning_dirs(root)
            observations = paths["observations"]
            observations.write_text("tracked\n", encoding="utf-8")
            (root / ".gitignore").write_text(".omx/\n", encoding="utf-8")
            added = subprocess.run(
                ["git", "add", "--force", ".omx/learning/observations.jsonl"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            payload = {"session_id": "trace", "cwd": str(root), "tool_name": "Bash"}

            result = self.run_observer(
                root,
                json.dumps(payload),
                extra_env={"GIT_TRACE": str(observations)},
            )

            self.assert_policy_failure(result, "Git-tracked storage path is not allowed")
            self.assertEqual(observations.read_text(encoding="utf-8"), "tracked\n")

    def test_global_excludes_file_cannot_authorize_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            root = Path(tmp)
            fake_home = Path(home_tmp)
            self.init_git(root)
            excludes = fake_home / "global-ignore"
            excludes.write_text(".omx/\n", encoding="utf-8")
            (fake_home / ".gitconfig").write_text(
                f"[core]\n\texcludesFile = {excludes}\n", encoding="utf-8"
            )
            payload = {"session_id": "global-ignore", "cwd": str(root), "tool_name": "Bash"}

            result = self.run_observer(
                root,
                json.dumps(payload),
                extra_env={"HOME": str(fake_home), "XDG_CONFIG_HOME": str(fake_home)},
            )

            self.assert_policy_failure(result, "Git storage path must be ignored")
            self.assertFalse((root / ".omx").exists())

    def test_safe_non_system_effective_git_is_allowed(self) -> None:
        repo_root = SCRIPT.parents[3]
        with (
            tempfile.TemporaryDirectory() as project_tmp,
            tempfile.TemporaryDirectory(dir=repo_root) as install_tmp,
        ):
            project = Path(project_tmp)
            git = Path(install_tmp) / "bin" / "git"
            git.parent.mkdir()
            git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            git.chmod(0o755)

            with mock.patch.dict(os.environ, {"PATH": str(git.parent)}):
                resolved = insight_observer.resolve_git_executable(project)

            self.assertEqual(resolved, str(git.resolve()))

    def test_project_local_git_is_skipped_for_safe_candidate(self) -> None:
        repo_root = SCRIPT.parents[3]
        with (
            tempfile.TemporaryDirectory() as project_tmp,
            tempfile.TemporaryDirectory(dir=repo_root) as install_tmp,
        ):
            project = Path(project_tmp)
            project_git = project / "bin" / "git"
            project_git.parent.mkdir()
            project_git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            project_git.chmod(0o755)
            safe_git = Path(install_tmp) / "bin" / "git"
            safe_git.parent.mkdir()
            safe_git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            safe_git.chmod(0o755)
            path = os.pathsep.join((str(project_git.parent), str(safe_git.parent)))

            with mock.patch.dict(os.environ, {"PATH": path}):
                resolved = insight_observer.resolve_git_executable(project)

            self.assertEqual(resolved, str(safe_git.resolve()))

    def test_case_alias_project_local_git_is_skipped_for_safe_candidate(self) -> None:
        repo_root = SCRIPT.parents[3]
        with (
            tempfile.TemporaryDirectory() as parent_tmp,
            tempfile.TemporaryDirectory(dir=repo_root) as install_tmp,
        ):
            parent = Path(parent_tmp)
            project = parent / "CaseProject"
            project.mkdir()
            case_alias = parent / "cASEpROJECT"
            try:
                if not project.samefile(case_alias):
                    self.skipTest("filesystem does not provide case-insensitive aliases")
            except FileNotFoundError:
                self.skipTest("filesystem is case-sensitive")
            project_git = project / "bin" / "git"
            project_git.parent.mkdir()
            project_git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            project_git.chmod(0o755)
            safe_git = Path(install_tmp) / "bin" / "git"
            safe_git.parent.mkdir()
            safe_git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            safe_git.chmod(0o755)
            path = os.pathsep.join((str(case_alias / "bin"), str(safe_git.parent)))

            with mock.patch.dict(os.environ, {"PATH": path}):
                resolved = insight_observer.resolve_git_executable(project)

            self.assertEqual(resolved, str(safe_git.resolve()))

    def test_writable_git_path_is_skipped_for_safe_candidate(self) -> None:
        repo_root = SCRIPT.parents[3]
        with (
            tempfile.TemporaryDirectory() as project_tmp,
            tempfile.TemporaryDirectory(dir=repo_root) as unsafe_tmp,
            tempfile.TemporaryDirectory(dir=repo_root) as safe_tmp,
        ):
            project = Path(project_tmp)
            unsafe_git = Path(unsafe_tmp) / "bin" / "git"
            unsafe_git.parent.mkdir()
            unsafe_git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            unsafe_git.chmod(0o755)
            unsafe_git.parent.chmod(0o777)
            safe_git = Path(safe_tmp) / "bin" / "git"
            safe_git.parent.mkdir()
            safe_git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            safe_git.chmod(0o755)
            path = os.pathsep.join((str(unsafe_git.parent), str(safe_git.parent)))

            with mock.patch.dict(os.environ, {"PATH": path}):
                resolved = insight_observer.resolve_git_executable(project)

            self.assertEqual(resolved, str(safe_git.resolve()))

    def test_writable_git_executable_is_skipped_for_safe_candidate(self) -> None:
        repo_root = SCRIPT.parents[3]
        with (
            tempfile.TemporaryDirectory() as project_tmp,
            tempfile.TemporaryDirectory(dir=repo_root) as unsafe_tmp,
            tempfile.TemporaryDirectory(dir=repo_root) as safe_tmp,
        ):
            project = Path(project_tmp)
            unsafe_git = Path(unsafe_tmp) / "bin" / "git"
            unsafe_git.parent.mkdir()
            unsafe_git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            unsafe_git.chmod(0o777)
            safe_git = Path(safe_tmp) / "bin" / "git"
            safe_git.parent.mkdir()
            safe_git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            safe_git.chmod(0o755)
            path = os.pathsep.join((str(unsafe_git.parent), str(safe_git.parent)))

            with mock.patch.dict(os.environ, {"PATH": path}):
                resolved = insight_observer.resolve_git_executable(project)

            self.assertEqual(resolved, str(safe_git.resolve()))

    def test_owned_git_below_sticky_ancestor_is_allowed(self) -> None:
        with (
            tempfile.TemporaryDirectory() as project_tmp,
            tempfile.TemporaryDirectory(dir="/tmp") as install_tmp,
        ):
            project = Path(project_tmp)
            git = Path(install_tmp) / "private" / "bin" / "git"
            git.parent.mkdir(parents=True, mode=0o700)
            git.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            git.chmod(0o755)

            with mock.patch.dict(os.environ, {"PATH": str(git.parent)}):
                resolved = insight_observer.resolve_git_executable(project)

            self.assertEqual(resolved, str(git.resolve()))

    def test_git_path_rejects_untrusted_file_or_directory_owner(self) -> None:
        git = Path("/trusted-toolchain/bin/git")
        trusted_uid = 501
        foreign_uid = 502
        checked_components = (git, git.parent, git.parent.parent)

        for foreign_component in checked_components:

            def fake_stat(component: Path, *args: object, **kwargs: object) -> os.stat_result:
                del args, kwargs
                is_file = component == git
                mode = (stat.S_IFREG if is_file else stat.S_IFDIR) | 0o755
                uid = 0 if component == Path("/") else trusted_uid
                if component == foreign_component:
                    uid = foreign_uid
                return os.stat_result((mode, 0, 0, 1, uid, 0, 0, 0, 0, 0))

            with (
                self.subTest(component=foreign_component),
                mock.patch.object(insight_observer.os, "geteuid", return_value=trusted_uid),
                mock.patch.object(Path, "stat", autospec=True, side_effect=fake_stat),
            ):
                self.assertFalse(insight_observer.trusted_git_path(git))

    def test_git_unignored_observations_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            paths = insight_observer.learning_dirs(root)

            with self.assertRaises(insight_observer.UnsafeStoragePath):
                insight_observer.append_jsonl(paths["observations"], {"session_id": "s"}, root)

            self.assertFalse(paths["observations"].exists())

    def test_git_unignored_hook_preflight_leaves_no_storage_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            payload = {"session_id": "unignored", "cwd": str(root), "tool_name": "Bash"}

            result = self.run_observer(root, json.dumps(payload))

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / ".omx").exists())

    def test_git_stop_preflights_candidate_before_storage_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            (root / ".gitignore").write_text(".omx/learning/observations.jsonl\n", encoding="utf-8")
            payload = {"session_id": "candidate", "cwd": str(root), "tool_name": "Stop"}

            result = self.run_observer(root, json.dumps(payload), phase="stop")

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / ".omx").exists())

    def test_git_unignored_candidate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            (root / ".gitignore").write_text(".omx/learning/observations.jsonl\n", encoding="utf-8")
            paths = insight_observer.learning_dirs(root)
            observation = {
                "session_id": "session-candidate",
                "project_id": "project",
                "project_root": "[project-root]",
            }
            insight_observer.append_jsonl(paths["observations"], observation, root)

            with (
                mock.patch.object(insight_observer, "slug_timestamp", return_value="fixed"),
                self.assertRaises(insight_observer.UnsafeStoragePath),
            ):
                insight_observer.write_stop_candidate(paths, observation)

            self.assertEqual(list(paths["candidates"].glob("*.md")), [])

    def test_git_ignored_storage_allows_observations_and_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            (root / ".gitignore").write_text(".omx/\n", encoding="utf-8")
            payload = {"session_id": "ignored", "cwd": str(root), "tool_name": "Stop"}

            result = self.run_observer(root, json.dumps(payload), phase="stop")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / ".omx" / "learning" / "observations.jsonl").is_file())
            self.assertEqual(len(list((root / ".omx" / "learning" / "candidates").glob("*.md"))), 1)

    def test_git_ignored_outer_repo_rejects_nested_omx_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            (root / ".gitignore").write_text(".omx/\n", encoding="utf-8")
            nested = root / ".omx"
            nested.mkdir()
            self.init_git(nested)
            payload = {"session_id": "nested", "cwd": str(root), "tool_name": "Bash"}

            result = self.run_observer(root, json.dumps(payload))

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((nested / "learning").exists())

    def test_gitlink_storage_prefix_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            (root / ".gitignore").write_text(".omx/\n", encoding="utf-8")
            self.add_gitlink(root, ".omx")
            payload = {"session_id": "gitlink", "cwd": str(root), "tool_name": "Bash"}

            result = self.run_observer(root, json.dumps(payload))

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / ".omx").exists())

    def test_descendant_gitlink_outside_storage_ancestors_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_git(root)
            (root / ".gitignore").write_text(".omx/\n", encoding="utf-8")
            self.add_gitlink(root, ".omx/unrelated")
            payload = {"session_id": "sibling-gitlink", "cwd": str(root), "tool_name": "Bash"}

            result = self.run_observer(root, json.dumps(payload))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / ".omx" / "learning" / "observations.jsonl").is_file())

    def test_git_policy_probe_failures_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            target = root / ".omx" / "learning" / "observations.jsonl"
            for error in (
                FileNotFoundError("git"),
                subprocess.TimeoutExpired(cmd=["git"], timeout=3),
            ):
                with (
                    self.subTest(error=type(error).__name__),
                    mock.patch.object(insight_observer.subprocess, "run", side_effect=error),
                    self.assertRaises(insight_observer.UnsafeStoragePath),
                ):
                    insight_observer.require_git_ignored_untracked(target, root)

            with (
                mock.patch.object(insight_observer.shutil, "which", return_value=None),
                self.assertRaises(insight_observer.UnsafeStoragePath),
            ):
                insight_observer.require_git_ignored_untracked(target, root)

    def test_non_git_probe_accepts_only_known_filesystem_boundary_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            target = root / ".omx" / "learning" / "observations.jsonl"
            fatal = "fatal: not a git repository (or any of the parent directories): .git"
            boundary = "Stopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set)."
            allowed = subprocess.CompletedProcess(
                ["git"], returncode=128, stdout="", stderr=f"{fatal}\n{boundary}\n"
            )
            with mock.patch.object(insight_observer.subprocess, "run", return_value=allowed):
                insight_observer.require_git_ignored_untracked(target, root)

            rejected = subprocess.CompletedProcess(
                ["git"], returncode=128, stdout="", stderr=f"{fatal}\nunexpected detail\n"
            )
            with (
                mock.patch.object(insight_observer.subprocess, "run", return_value=rejected),
                self.assertRaises(insight_observer.UnsafeStoragePath),
            ):
                insight_observer.require_git_ignored_untracked(target, root)

            for stderr in (
                "fatal: detected dubious ownership in repository",
                "fatal: bad object HEAD",
                "fatal: unexpected policy failure",
            ):
                failed = subprocess.CompletedProcess(
                    ["git"], returncode=128, stdout="", stderr=stderr
                )
                with (
                    self.subTest(stderr=stderr),
                    mock.patch.object(insight_observer.subprocess, "run", return_value=failed),
                    self.assertRaises(insight_observer.UnsafeStoragePath),
                ):
                    insight_observer.require_git_ignored_untracked(target, root)

    def test_explicit_git_environment_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            target = root / ".omx" / "learning" / "observations.jsonl"
            for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_LITERAL_PATHSPECS"):
                with (
                    self.subTest(name=name),
                    mock.patch.dict(os.environ, {name: "/missing-git-context"}),
                    self.assertRaises(insight_observer.UnsafeStoragePath),
                ):
                    insight_observer.require_git_ignored_untracked(target, root)

    def test_benign_git_config_environment_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            target = root / ".omx" / "learning" / "observations.jsonl"
            fatal = "fatal: not a git repository (or any of the parent directories): .git"
            completed = subprocess.CompletedProcess(
                ["git"], returncode=128, stdout="", stderr=f"{fatal}\n"
            )
            inherited_config = {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": "/attacker/global-config",
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.excludesFile",
                "GIT_CONFIG_VALUE_0": "/attacker/global-ignore",
            }
            with (
                mock.patch.dict(os.environ, inherited_config),
                mock.patch.object(
                    insight_observer.subprocess, "run", return_value=completed
                ) as run,
            ):
                insight_observer.require_git_ignored_untracked(target, root)

            child_env = run.call_args.kwargs["env"]
            self.assertEqual(child_env["GIT_CONFIG_NOSYSTEM"], "1")
            self.assertEqual(child_env["GIT_CONFIG_GLOBAL"], os.devnull)
            for name in ("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"):
                self.assertNotIn(name, child_env)

    def test_true_non_git_root_is_allowed_by_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            target = root / ".omx" / "learning" / "observations.jsonl"

            insight_observer.require_git_ignored_untracked(target, root)

            self.assertFalse((root / ".omx").exists())

    def test_rejects_symlinked_candidate_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = insight_observer.learning_dirs(root)
            target = root / "candidate-target"
            target.write_text("unchanged", encoding="utf-8")
            session_id = "session-safe"
            candidate = paths["candidates"] / "fixed-session-safe.md"
            candidate.symlink_to(target)
            observation = {
                "session_id": session_id,
                "project_id": "project",
                "project_root": "[project-root]",
            }
            with mock.patch.object(insight_observer, "slug_timestamp", return_value="fixed"):
                with self.assertRaises(insight_observer.UnsafeStoragePath):
                    insight_observer.write_stop_candidate(paths, observation)
            self.assertEqual(target.read_text(encoding="utf-8"), "unchanged")

    def test_dry_run_prints_observation_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = os.environ.copy()
            env["CODEX_INSIGHTS_PROJECT_DIR"] = str(root)
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
            self.assertTrue(row["session_id"].startswith("session-"))
            self.assertNotEqual(row["session_id"], "s-dry")
            self.assertFalse((root / ".omx").exists())
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
            rows = [
                json.loads(line)
                for line in observation_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(rows[0]["session_id"], "existing")
            self.assertTrue(rows[1]["session_id"].startswith("session-"))

    def test_stop_candidate_paths_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = insight_observer.learning_dirs(root)
            first = insight_observer.unique_candidate_path(paths["candidates"], "same-session")
            first.write_text("existing", encoding="utf-8")
            second = insight_observer.unique_candidate_path(paths["candidates"], "same-session")
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
                extra_env={
                    "CODEX_INSIGHTS_SCOPE_ROOT": str(root),
                    "CODEX_INSIGHTS_PROJECT_DIR": "",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / ".omx" / "learning" / "observations.jsonl").exists())

    def test_env_project_dir_mismatch_falls_back_to_event_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            event_root = Path(tmp)
            env_root = Path(other)
            payload = {"session_id": "s-env", "cwd": str(event_root), "tool_name": "Bash"}
            result = self.run_observer(
                env_root,
                json.dumps(payload),
                extra_env={"CODEX_INSIGHTS_PROJECT_DIR": str(env_root)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((env_root / ".omx" / "learning" / "observations.jsonl").exists())
            row = json.loads((event_root / ".omx" / "learning" / "observations.jsonl").read_text())
            self.assertEqual(row["root_source"], "cwd-fallback")
            self.assertEqual(row["root_warning"], "env-project-dir-rejected")

    def test_legacy_environment_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"session_id": "legacy", "tool_name": "Bash"}
            env = os.environ.copy()
            env.pop("CODEX_INSIGHTS_PROJECT_DIR", None)
            env["SESSION_LEARNING_PROJECT_DIR"] = str(root)
            env["SESSION_LEARNING_SOURCE"] = "legacy-hook"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--phase", "post"],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            row = json.loads((root / ".omx" / "learning" / "observations.jsonl").read_text())
            self.assertEqual(row["root_source"], "env")
            self.assertEqual(row["source"], "configured")

    def test_legacy_disabled_flag_skips_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"session_id": "legacy-disabled", "cwd": str(root), "tool_name": "Bash"}
            result = self.run_observer(
                root,
                json.dumps(payload),
                extra_env={"SESSION_LEARNING_DISABLED": "1"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / ".omx" / "learning" / "observations.jsonl").exists())

    def test_legacy_scope_root_skips_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            env = os.environ.copy()
            env.pop("CODEX_INSIGHTS_SCOPE_ROOT", None)
            env["SESSION_LEARNING_SCOPE_ROOT"] = str(root)
            payload = {"session_id": "legacy-scope", "cwd": str(outside), "tool_name": "Bash"}
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--phase", "post"],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / ".omx" / "learning" / "observations.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
