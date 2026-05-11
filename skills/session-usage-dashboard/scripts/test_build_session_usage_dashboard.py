#!/usr/bin/env python3
"""Tests for build_session_usage_dashboard.py."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("build_session_usage_dashboard.py")
SPEC = importlib.util.spec_from_file_location("dashboard", SCRIPT)
assert SPEC and SPEC.loader
dashboard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dashboard)


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def test_codex_and_claude_counts_and_offline_outputs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        codex = root / "codex.jsonl"
        claude = root / "claude.jsonl"
        out = root / "out"
        write_jsonl(
            codex,
            [
                {
                    "timestamp": "2026-05-10T00:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "codex-1",
                        "cwd": "/workspace",
                        "thread_source": "subagent",
                        "source": {"subagent": {"other": "guardian"}},
                    },
                },
                {
                    "timestamp": "2026-05-10T00:01:00Z",
                    "type": "response_item",
                    "payload": {"type": "function_call", "name": "exec_command", "arguments": "SECRET_TOKEN=abc"},
                },
                {
                    "timestamp": "2026-05-10T00:02:00Z",
                    "type": "response_item",
                    "payload": {"type": "custom_tool_call", "name": "apply_patch", "input": "password=secret"},
                },
                {
                    "timestamp": "2026-05-10T00:03:00Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "[$skill-creator] use $session-usage-dashboard SECRET_TOKEN"}],
                    },
                },
            ],
        )
        write_jsonl(
            claude,
            [
                {
                    "timestamp": "2026-05-10T00:04:00Z",
                    "type": "assistant",
                    "sessionId": "claude-1",
                    "attributionSkill": "simplify",
                    "attributionAgent": "Explore",
                    "isSidechain": True,
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "name": "Bash", "id": "tool-1", "input": {"command": "echo SECRET_TOKEN"}},
                            {
                                "type": "tool_use",
                                "name": "Agent",
                                "id": "tool-2",
                                "input": {"subagent_type": "planner", "prompt": "SECRET_TOKEN"},
                            },
                        ],
                    },
                }
            ],
        )
        collector = dashboard.UsageCollector()
        dashboard.parse_codex(codex, collector)
        dashboard.parse_claude(claude, collector)
        summary = dashboard.build_summary(collector)
        assert summary["totals"]["unique_tools"] == 4
        assert {"provider": "codex", "name": "exec_command", "count": 1} in summary["tools"]
        assert {"provider": "codex", "name": "apply_patch", "count": 1} in summary["tools"]
        assert {"provider": "claude", "name": "Bash", "count": 1} in summary["tools"]
        assert {"provider": "claude", "name": "Agent", "count": 1} in summary["tools"]
        assert {"provider": "codex", "name": "skill-creator", "count": 1} in summary["skills"]
        assert {"provider": "codex", "name": "session-usage-dashboard", "count": 1} in summary["skills"]
        assert {"provider": "claude", "name": "simplify", "count": 1} in summary["skills"]
        assert {"provider": "codex", "name": "guardian", "count": 1} in summary["subagents"]
        assert {"provider": "claude", "name": "planner", "count": 1} in summary["subagents"]
        summary_path, html_path = dashboard.write_outputs(summary, out)
        html = html_path.read_text(encoding="utf-8")
        summary_text = summary_path.read_text(encoding="utf-8")
        forbidden = ("SECRET_TOKEN", "password=secret", "fetch(", "XMLHttpRequest", "http://", "https://", "<script src=")
        for marker in forbidden:
            assert marker not in html
            assert marker not in summary_text
        assert "connect-src 'none'" in html


def test_missing_inputs_warn_without_crashing() -> None:
    collector = dashboard.UsageCollector()
    summary = dashboard.build_summary(collector)
    assert summary["totals"]["events"] == 0
    assert dashboard.validate_offline_html("<html><body>ok</body></html>") == []


if __name__ == "__main__":
    test_codex_and_claude_counts_and_offline_outputs()
    test_missing_inputs_warn_without_crashing()
    print("ok")
