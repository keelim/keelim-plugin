#!/usr/bin/env python3
"""Smoke tests for render_html_report.py."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import tempfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("render_html_report.py")
SPEC = importlib.util.spec_from_file_location("render_html_report", SCRIPT_PATH)
assert SPEC and SPEC.loader
render_html_report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_html_report)


def test_demo_report_renders_and_validates() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "demo.html"
        demo = SCRIPT_PATH.parents[1] / "examples" / "demo-report.json.sample"
        assert render_html_report.main(
            ["--input", str(demo), "--output", str(output), "--validate", "--allow-outside-output"]
        ) == 0
        assert output.exists()
        assert render_html_report.check_html(output) == []


def test_rendering_escapes_text_and_omits_remote_urls() -> None:
    payload = {
        "title": "<Report>",
        "summary": "See https://example.invalid/report",
        "sections": [{"heading": "Safety", "body": "<script>alert(1)</script>"}],
    }
    html = render_html_report.render_html(payload)
    assert "&lt;Report&gt;" in html
    assert "https://" not in html
    assert "[remote-url-omitted]" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert render_html_report.check_html_text(html) == []


def test_validator_rejects_remote_assets_and_network_apis() -> None:
    unsafe = """
    <!doctype html>
    <meta http-equiv="Content-Security-Policy" content="connect-src 'none'">
    <link href="style.css">
    <script src="app.js"></script>
    <img src="https://example.invalid/image.png">
    <img src="//cdn.invalid/image.png">
    <style>.bad { background-image: url(//cdn.invalid/a.png); }</style>
    <iframe srcdoc="x"></iframe>
    <script>fetch('/data'); navigator.sendBeacon('/x');</script>
    """
    issues = render_html_report.check_html_text(unsafe)
    assert any("external link href" in issue for issue in issues)
    assert any("external script src" in issue for issue in issues)
    assert any("remote URL" in issue for issue in issues)
    assert any("protocol-relative asset URL" in issue for issue in issues)
    assert any("protocol-relative CSS URL" in issue for issue in issues)
    assert any("iframe" in issue for issue in issues)
    assert any("fetch(" in issue for issue in issues)
    assert any("sendBeacon" in issue for issue in issues)


def test_cli_check_html_fails_for_unsafe_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        unsafe = Path(tmp) / "unsafe.html"
        unsafe.write_text("<script src=\"app.js\"></script>", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            assert render_html_report.main(["--check-html", str(unsafe)]) == 1


def test_validate_failure_does_not_write_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        payload = root / "report.json"
        template = root / "template.html"
        output = root / "unsafe.html"
        payload.write_text(json.dumps({"title": "Unsafe"}), encoding="utf-8")
        template.write_text(
            "<!doctype html><meta http-equiv=\"Content-Security-Policy\" content=\"connect-src 'none'\">"
            "<script src=\"app.js\"></script>__REPORT_BODY__",
            encoding="utf-8",
        )
        with contextlib.redirect_stderr(io.StringIO()):
            code = render_html_report.main(
                ["--input", str(payload), "--output", str(output), "--validate", "--template", str(template)]
            )
        assert code == 1
        assert not output.exists()


def test_output_outside_input_dir_requires_explicit_flag() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        input_dir = root / "input"
        output_dir = root / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        payload = input_dir / "report.json"
        output = output_dir / "report.html"
        payload.write_text(json.dumps({"title": "Safe"}), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            code = render_html_report.main(["--input", str(payload), "--output", str(output)])
        assert code == 1
        assert not output.exists()

def main() -> int:
    test_demo_report_renders_and_validates()
    test_rendering_escapes_text_and_omits_remote_urls()
    test_validator_rejects_remote_assets_and_network_apis()
    test_cli_check_html_fails_for_unsafe_file()
    test_validate_failure_does_not_write_output()
    test_output_outside_input_dir_requires_explicit_flag()
    print("render_html_report smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
