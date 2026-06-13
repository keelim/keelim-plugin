#!/usr/bin/env python3
"""Security regression tests for repo-level runner scripts."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


promote = load_module("promote_plugin_skills", SCRIPTS_DIR / "promote_plugin_skills.py")
agent_runner = load_module(
    "skillopt_agent_instructions", SCRIPTS_DIR / "skillopt_agent_instructions.py"
)
plugin_runner = load_module("skillopt_plugin_skills", SCRIPTS_DIR / "skillopt_plugin_skills.py")


class PromoteSecurityTests(unittest.TestCase):
    def test_explicit_candidate_must_stay_under_candidate_root_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_root = root / "allowed"
            outside = root / "outside.md"
            outside.write_text(
                "---\nname: tech-post-maker\ndescription: x\n---\n\nbody\n", encoding="utf-8"
            )
            with self.assertRaises(SystemExit):
                promote.ensure_safe_candidate(outside, [candidate_root], allow_external=False)
            self.assertEqual(
                promote.ensure_safe_candidate(outside, [candidate_root], allow_external=True),
                outside.resolve(),
            )

    def test_stage_root_must_stay_under_promote_candidates_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside-stage"
            with self.assertRaises(SystemExit):
                promote.resolve_stage_root(str(outside), "run", allow_external=False)


class SkillOptSecurityTests(unittest.TestCase):
    def test_agent_runner_env_uses_allowlist_and_scrubs_model_provider_keys(self) -> None:
        original = os.environ.copy()
        try:
            os.environ.clear()
            os.environ.update(
                {
                    "PATH": original.get("PATH", ""),
                    "OPENAI_API_KEY": "secret",
                    "CODEX_EXEC_PATH": "/tmp/not-codex",
                    "UNRELATED_SECRET": "secret",
                }
            )
            env = agent_runner.codex_only_env()
            self.assertEqual(env["CODEX_EXEC_PATH"], "codex")
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("UNRELATED_SECRET", env)
        finally:
            os.environ.clear()
            os.environ.update(original)

    def test_custom_codex_exec_requires_trust_env(self) -> None:
        original = os.environ.copy()
        try:
            os.environ.pop(agent_runner.TRUST_CODEX_EXEC_ENV, None)
            with self.assertRaises(SystemExit):
                agent_runner.ensure_tool("/tmp/codex")
        finally:
            os.environ.clear()
            os.environ.update(original)

    def test_plugin_runner_verifies_pinned_skillopt_revision(self) -> None:
        self.assertEqual(
            plugin_runner.EXPECTED_SKILLOPT_REV, "ee9931ec017cd8d9ce7caab272983e268258ddf5"
        )


if __name__ == "__main__":
    unittest.main()
