#!/usr/bin/env python3
"""Focused tests for local SkillOpt overlay dataloaders, evaluators, and backend."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_OVERLAY = EVAL_ROOT = ROOT / "evals" / "skillopt" / "plugin-skill-improver" / "overlays"
AGENT_OVERLAY = ROOT / "evals" / "skillopt" / "agent-instructions-improver" / "overlays"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PLUGIN_DATALOADER = load_module(
    "plugin_dataloader",
    PLUGIN_OVERLAY / "skillopt" / "envs" / "plugin_skill_improver" / "dataloader.py",
)
PLUGIN_EVALUATOR = load_module(
    "plugin_evaluator",
    PLUGIN_OVERLAY / "skillopt" / "envs" / "plugin_skill_improver" / "evaluator.py",
)
AGENT_DATALOADER = load_module(
    "agent_dataloader",
    AGENT_OVERLAY / "skillopt" / "envs" / "agent_instructions_improver" / "dataloader.py",
)
AGENT_EVALUATOR = load_module(
    "agent_evaluator",
    AGENT_OVERLAY / "skillopt" / "envs" / "agent_instructions_improver" / "evaluator.py",
)
CODEX_BACKEND = load_module(
    "codex_chat_backend",
    AGENT_OVERLAY / "skillopt" / "model" / "codex_chat_backend.py",
)


class DataloaderTests(unittest.TestCase):
    def assert_loader_formats(self, loader: ModuleType) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            list_path = root / "items.json"
            list_path.write_text(json.dumps([{"id": "one"}, {"id": "two"}]), encoding="utf-8")
            self.assertEqual([item["id"] for item in loader.load_items(list_path)], ["one", "two"])

            wrapped_path = root / "wrapped.json"
            wrapped_path.write_text(json.dumps({"items": [{"id": "wrapped"}]}), encoding="utf-8")
            self.assertEqual(loader.load_items(wrapped_path)[0]["id"], "wrapped")

            jsonl_path = root / "items.jsonl"
            jsonl_path.write_text('{"id":"a"}\n{"id":"b"}\n', encoding="utf-8")
            self.assertEqual([item["id"] for item in loader.load_items(jsonl_path)], ["a", "b"])

            empty_path = root / "empty.json"
            empty_path.write_text("\n", encoding="utf-8")
            self.assertEqual(loader.load_items(empty_path), [])

            bad_path = root / "bad.json"
            bad_path.write_text('{"unexpected": true}', encoding="utf-8")
            with self.assertRaises(ValueError):
                loader.load_items(bad_path)

    def test_plugin_loader_supports_json_jsonl_and_wrappers(self) -> None:
        self.assert_loader_formats(PLUGIN_DATALOADER)

    def test_agent_loader_supports_json_jsonl_and_wrappers(self) -> None:
        self.assert_loader_formats(AGENT_DATALOADER)


class EvaluatorTests(unittest.TestCase):
    def assert_substring_scoring(self, evaluator: ModuleType) -> None:
        expected = {
            "must_find": ["AGENTS.md", "copy paste"],
            "must_not_claim": ["OpenAI API key is required"],
            "must_not_do": ["rewrite unrelated files"],
        }
        passing = evaluator.evaluate("Use agents.md and add COPY   PASTE commands.", expected)
        self.assertEqual(passing["hard"], 1)
        self.assertEqual(passing["missing"], [])

        missing = evaluator.evaluate("Use AGENTS.md only.", expected)
        self.assertEqual(missing["hard"], 0)
        self.assertIn("copy paste", missing["missing"])

        forbidden = evaluator.evaluate(
            "Use AGENTS.md, add copy paste commands, and claim OpenAI API key is required.",
            expected,
        )
        self.assertEqual(forbidden["hard"], 0)
        self.assertIn("OpenAI API key is required", forbidden["violations"])

    def test_plugin_evaluator_substring_scoring(self) -> None:
        self.assert_substring_scoring(PLUGIN_EVALUATOR)

    def test_agent_evaluator_substring_scoring(self) -> None:
        self.assert_substring_scoring(AGENT_EVALUATOR)


class CodexBackendCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        self._deployment = CODEX_BACKEND._OPTIMIZER_DEPLOYMENT

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        CODEX_BACKEND._OPTIMIZER_DEPLOYMENT = self._deployment

    def test_codex_command_defaults_are_locked_down(self) -> None:
        for key in list(os.environ):
            if key.startswith("CODEX_EXEC_") or key == "CODEX_OPTIMIZER_MODEL":
                os.environ.pop(key, None)
        CODEX_BACKEND._OPTIMIZER_DEPLOYMENT = ""
        cmd = CODEX_BACKEND._codex_command("prompt", Path("out.txt"), Path("/tmp/work"))
        self.assertEqual(cmd[:6], ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--color", "never"])
        self.assertIn("--sandbox", cmd)
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "workspace-write")
        self.assertIn("-C", cmd)
        self.assertEqual(cmd[cmd.index("-C") + 1], "/tmp/work")
        self.assertIn('approval_policy="never"', cmd)
        self.assertIn("network_access=false", cmd)
        self.assertIn('model_reasoning_effort="medium"', cmd)
        self.assertNotIn("-p", cmd)
        self.assertNotIn("-m", cmd)
        self.assertEqual(cmd[-1], "prompt")

    def test_codex_command_honors_env_profile_and_deployment(self) -> None:
        os.environ.update(
            {
                "CODEX_EXEC_PATH": "/bin/codex-test",
                "CODEX_EXEC_SANDBOX": "read-only",
                "CODEX_EXEC_APPROVAL_POLICY": "on-request",
                "CODEX_EXEC_NETWORK_ACCESS": "true",
                "CODEX_EXEC_REASONING_EFFORT": "high",
                "CODEX_EXEC_PROFILE": "local-profile",
                "CODEX_OPTIMIZER_MODEL": "env-model",
            }
        )
        CODEX_BACKEND._OPTIMIZER_DEPLOYMENT = "deployment-model"
        cmd = CODEX_BACKEND._codex_command("prompt", Path("out.txt"), Path("/tmp/work"))
        self.assertEqual(cmd[0], "/bin/codex-test")
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "read-only")
        self.assertIn('approval_policy="on-request"', cmd)
        self.assertIn("network_access=true", cmd)
        self.assertIn('model_reasoning_effort="high"', cmd)
        self.assertEqual(cmd[cmd.index("-p") + 1], "local-profile")
        self.assertEqual(cmd[cmd.index("-m") + 1], "deployment-model")


if __name__ == "__main__":
    unittest.main()
