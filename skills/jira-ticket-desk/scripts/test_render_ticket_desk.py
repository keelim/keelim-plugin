#!/usr/bin/env python3
"""Smoke tests for render_ticket_desk.py."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("render_ticket_desk.py")
SPEC = importlib.util.spec_from_file_location("render_ticket_desk", SCRIPT_PATH)
assert SPEC and SPEC.loader
render_ticket_desk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_ticket_desk)


def test_demo_html_is_offline() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "desk.html"
        assert render_ticket_desk.main(["--demo", "--output", str(output)]) == 0
        assert output.exists()
        assert render_ticket_desk.check_html(output) == []


def test_local_rules_override_bucket_and_reason() -> None:
    payload = [
        {
            "key": "APP-9",
            "summary": "Ticket intentionally not handled here",
            "status": "Open",
            "assignee": "Keelim",
            "priority": "Low",
        }
    ]
    rules = {
        "tickets": {
            "APP-9": {
                "bucket": "ignored",
                "reason": "belongs to the platform desk",
                "review_after": "2026-05-31",
            }
        }
    }

    data = render_ticket_desk.build_desk_data(payload, render_ticket_desk.load_rules_from_object(rules))
    assert data["tickets"][0]["bucket"] == "ignored"
    assert data["tickets"][0]["reason"] == "belongs to the platform desk"


def test_remote_urls_are_omitted_from_display_text() -> None:
    payload = [
        {
            "key": "APP-10",
            "summary": "Check https://jira.example/browse/APP-10",
            "status": "Open",
            "assignee": "Keelim",
            "priority": "Medium",
            "labels": ["https://example.invalid/label"],
        }
    ]
    data = render_ticket_desk.build_desk_data(payload, {})
    content = render_ticket_desk.render_html(data)
    assert "https://" not in content
    assert "[remote-url-omitted]" in content


def test_data_json_can_be_swapped_into_template() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_path = Path(tmp) / "ticket-desk.data.json"
        output = Path(tmp) / "ticket-desk.html"
        assert render_ticket_desk.main(["--demo", "--data-output", str(data_path)]) == 0
        assert data_path.exists()
        assert render_ticket_desk.main(["--data", str(data_path), "--output", str(output)]) == 0
        assert output.exists()
        assert render_ticket_desk.check_html(output) == []


def main() -> int:
    test_demo_html_is_offline()
    test_local_rules_override_bucket_and_reason()
    test_remote_urls_are_omitted_from_display_text()
    test_data_json_can_be_swapped_into_template()
    print("render_ticket_desk smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
