#!/usr/bin/env python3
"""Tests for build_session_usage_dashboard.py."""

from __future__ import annotations

import importlib.util
import json
import os
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
        out = root / ".omx" / "session-usage" / "out"
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
        dashboard.parse_codex(codex, collector, root)
        dashboard.parse_claude(claude, collector, root)
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


def test_authorization_header_token_is_redacted() -> None:
    sample_value = "abcdefghijklmnopqrstuvwxyz"
    text = dashboard.safe_text(f"Authorization: Bearer {sample_value}")
    assert sample_value not in text
    assert "[REDACTED]" in text


def test_json_key_and_long_token_values_are_redacted() -> None:
    sample_value = "abcdefghijklmnopqrstuvwxyz0123456789"
    text = dashboard.safe_text({"nested": {"api_key": sample_value}, "value": f"Bearer {sample_value}"}, 400)
    assert sample_value not in text
    assert "[REDACTED]" in text


def test_display_path_avoids_absolute_home_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "session.jsonl"
        path.write_text("", encoding="utf-8")
        collector = dashboard.UsageCollector()
        collector.add_input("codex", path, root)
        assert collector.input_files == [{"provider": "codex", "path": "session.jsonl"}]


def test_find_current_codex_respects_scan_limit(monkeypatch=None) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sessions = root / ".codex" / "sessions" / "2026" / "06" / "12"
        sessions.mkdir(parents=True)
        old = sessions / "old.jsonl"
        new = sessions / "new.jsonl"
        write_jsonl(old, [{"type": "session_meta", "payload": {"cwd": "/wanted"}}])
        write_jsonl(new, [{"type": "session_meta", "payload": {"cwd": "/other"}}])
        # Consecutive touches can share a timestamp on coarse filesystems.
        os.utime(old, (1_700_000_000, 1_700_000_000))
        os.utime(new, (1_700_000_060, 1_700_000_060))
        original_home = Path.home
        Path.home = classmethod(lambda cls: root)  # type: ignore[method-assign]
        try:
            assert dashboard.find_current_codex(Path("/wanted"), scan_limit=1) == []
            assert dashboard.find_current_codex(Path("/wanted"), scan_limit=1, include_any_cwd=True) == [new]
            assert dashboard.find_current_codex(Path("/wanted"), scan_limit=2) == [old]
        finally:
            Path.home = original_home  # type: ignore[method-assign]


def test_output_dir_must_stay_under_session_usage_without_override() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outside = root / "outside"
        try:
            dashboard.resolve_output_dir(str(outside), root, allow_outside_output=False)
        except SystemExit:
            pass
        else:
            raise AssertionError("outside output should be rejected")

        allowed = dashboard.resolve_output_dir(".omx/session-usage/current", root, allow_outside_output=False)
        assert allowed == (root / ".omx" / "session-usage" / "current").resolve()


if __name__ == "__main__":
    test_codex_and_claude_counts_and_offline_outputs()
    test_missing_inputs_warn_without_crashing()
    test_authorization_header_token_is_redacted()
    test_json_key_and_long_token_values_are_redacted()
    test_display_path_avoids_absolute_home_path()
    test_find_current_codex_respects_scan_limit()
    test_output_dir_must_stay_under_session_usage_without_override()
    print("ok")
