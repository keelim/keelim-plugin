#!/usr/bin/env python3
"""Smoke tests for local SkillOpt eval configs and fixtures."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = ROOT / "evals" / "skillopt"


def scalar_value(text: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", text, re.MULTILINE)
    if not match:
        raise AssertionError(f"missing key: {key}")
    return match.group(1).strip().strip("'\"")


def nested_int(text: str, section: str, key: str) -> int:
    match = re.search(
        rf"^{re.escape(section)}:\n(?:(?:  .+\n)*?)  {re.escape(key)}:\s*(\d+)\s*$",
        text,
        re.MULTILINE,
    )
    if not match:
        raise AssertionError(f"missing {section}.{key}")
    return int(match.group(1))


class EvalConfigTests(unittest.TestCase):
    def test_codex_configs_have_resolvable_base_and_holdout_counts(self) -> None:
        config_paths = sorted(EVAL_ROOT.glob("*/configs/*/codex_only.yaml"))
        self.assertGreaterEqual(len(config_paths), 2)
        for config_path in config_paths:
            with self.subTest(config=str(config_path.relative_to(ROOT))):
                text = config_path.read_text(encoding="utf-8")
                base = config_path.parent / scalar_value(text, "_base_")
                self.assertTrue(base.resolve().is_file(), base)
                self.assertGreater(nested_int(text, "evaluation", "sel_env_num"), 0)
                self.assertGreater(nested_int(text, "evaluation", "test_env_num"), 0)

    def test_score_fixture_samples_cover_multiple_cases(self) -> None:
        fixture_paths = sorted(EVAL_ROOT.glob("*/fixtures/score-fixture.json.sample"))
        self.assertGreaterEqual(len(fixture_paths), 2)
        for fixture_path in fixture_paths:
            with self.subTest(fixture=str(fixture_path.relative_to(ROOT))):
                payload = json.loads(fixture_path.read_text(encoding="utf-8"))
                items = payload.get("items") if isinstance(payload, dict) else payload
                self.assertIsInstance(items, list)
                self.assertGreaterEqual(len(items), 3)
                for item in items:
                    self.assertIn("response", item)
                    self.assertIn("expected", item)
                    self.assertTrue(item["expected"].get("must_find"))


if __name__ == "__main__":
    unittest.main()
