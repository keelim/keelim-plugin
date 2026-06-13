#!/usr/bin/env python3
"""Smoke tests for render_ticket_desk.py."""

from __future__ import annotations

import importlib.util
import json
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
        assert render_ticket_desk.main(["--demo", "--output", str(output), "--allow-outside-output"]) == 0
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


def test_unknown_rule_bucket_falls_back_to_next() -> None:
    payload = [
        {
            "key": "APP-11",
            "summary": "Blocked text should not override an explicit unknown bucket",
            "status": "Blocked",
            "assignee": "Keelim",
            "priority": "High",
        }
    ]
    rules = {"tickets": {"APP-11": {"bucket": "someday"}}}

    data = render_ticket_desk.build_desk_data(payload, render_ticket_desk.load_rules_from_object(rules))
    assert data["tickets"][0]["bucket"] == "next"


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


def test_offline_check_rejects_link_with_intervening_attributes() -> None:
    html = '<html><head><link rel="stylesheet" media="all" href="style.css"></head><body></body></html>'
    failures = render_ticket_desk.check_html_text(html)
    assert "external link href" in failures


def test_data_json_can_be_swapped_into_template() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_path = Path(tmp) / "ticket-desk.data.json"
        output = Path(tmp) / "ticket-desk.html"
        assert render_ticket_desk.main(["--demo", "--data-output", str(data_path), "--allow-outside-output"]) == 0
        assert data_path.exists()
        assert render_ticket_desk.main(["--data", str(data_path), "--output", str(output)]) == 0
        assert output.exists()
        assert render_ticket_desk.check_html(output) == []


def test_output_outside_input_dir_requires_explicit_flag() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        input_dir = root / "input"
        output_dir = root / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        data_path = input_dir / "ticket-desk.data.json"
        output = output_dir / "ticket-desk.html"
        data_path.write_text(json.dumps({"tickets": []}), encoding="utf-8")
        assert render_ticket_desk.main(["--data", str(data_path), "--output", str(output)]) == 1
        assert not output.exists()


def main() -> int:
    test_demo_html_is_offline()
    test_local_rules_override_bucket_and_reason()
    test_unknown_rule_bucket_falls_back_to_next()
    test_remote_urls_are_omitted_from_display_text()
    test_offline_check_rejects_link_with_intervening_attributes()
    test_data_json_can_be_swapped_into_template()
    test_output_outside_input_dir_requires_explicit_flag()
    print("render_ticket_desk smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
