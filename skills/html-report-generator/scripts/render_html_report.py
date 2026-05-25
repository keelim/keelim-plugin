#!/usr/bin/env python3
"""Render generic block-model JSON as a secure offline HTML report."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_PATH = SKILL_ROOT / "assets" / "report-template.html"
REMOTE_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
REMOTE_URL_ANYWHERE_RE = re.compile(r"https?://", re.IGNORECASE)


REPORT_CSS = """
:root {
  color-scheme: light;
  --bg: #f7f8f5;
  --ink: #20231f;
  --muted: #60675c;
  --line: #d9ddcf;
  --panel: #ffffff;
  --accent: #196b68;
  --accent-weak: #dcefed;
  --warn: #8a5a00;
  --danger: #a3372a;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
}
.report {
  max-width: 1120px;
  margin: 0 auto;
  padding: 40px 24px 56px;
}
.hero {
  border-bottom: 1px solid var(--line);
  padding-bottom: 22px;
  margin-bottom: 24px;
}
h1, h2, h3 { line-height: 1.2; margin: 0; }
h1 { font-size: 2.35rem; letter-spacing: 0; }
h2 { font-size: 1.18rem; margin-bottom: 12px; }
h3 { font-size: 1rem; margin-bottom: 8px; }
.subtitle {
  color: var(--accent);
  font-size: 1.05rem;
  margin: 10px 0 0;
}
.summary {
  color: var(--muted);
  max-width: 760px;
  margin: 14px 0 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  margin: 16px 0;
}
.metric-value {
  display: block;
  color: var(--accent);
  font-size: 1.7rem;
  font-weight: 700;
}
.metric-note, .muted { color: var(--muted); font-size: 0.92rem; }
.metadata {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 8px 16px;
}
.metadata dt { color: var(--muted); }
.metadata dd { margin: 0; }
.section-body p { margin: 0 0 10px; }
ul { margin: 8px 0 0 20px; padding: 0; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.94rem;
}
th, td {
  border-bottom: 1px solid var(--line);
  padding: 9px 8px;
  text-align: left;
  vertical-align: top;
}
th {
  color: var(--muted);
  font-weight: 650;
}
.finding {
  border-left: 4px solid var(--accent);
}
.finding.high, .finding.critical { border-left-color: var(--danger); }
.finding.medium { border-left-color: var(--warn); }
.severity {
  display: inline-block;
  color: var(--accent);
  background: var(--accent-weak);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
}
.local-ref {
  color: var(--accent);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  overflow-wrap: anywhere;
}
@media (max-width: 640px) {
  .report { padding: 28px 16px 40px; }
  h1 { font-size: 1.8rem; }
  .metadata { grid-template-columns: 1fr; gap: 2px; }
  table { display: block; overflow-x: auto; }
}
""".strip()


FORBIDDEN_HTML_SNIPPETS = (
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
    "EventSource",
    "sendBeacon",
    "@import",
)

FORBIDDEN_HTML_REGEXES = (
    (REMOTE_URL_ANYWHERE_RE, "remote URL"),
    (re.compile(r"\b(?:src|href)\s*=\s*['\"]//", re.IGNORECASE), "protocol-relative asset URL"),
    (re.compile(r"url\(\s*['\"]?//", re.IGNORECASE), "protocol-relative CSS URL"),
    (re.compile(r"<script\b[^>]*\bsrc\s*=", re.IGNORECASE), "external script src"),
    (re.compile(r"<link\b[^>]*\bhref\s*=", re.IGNORECASE), "external link href"),
    (re.compile(r"<iframe\b", re.IGNORECASE), "iframe"),
)


def load_json(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError("report JSON must be an object")
    return payload


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return REMOTE_URL_RE.sub("[remote-url-omitted]", str(value))


def h(value: Any) -> str:
    return escape(clean_text(value), quote=True)


def list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def list_of_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def render_paragraphs(value: Any) -> str:
    text = clean_text(value).strip()
    if not text:
        return ""
    parts = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return "".join(f"<p>{h(part)}</p>" for part in parts)


def render_items(items: Any) -> str:
    values = list_of_values(items)
    if not values:
        return ""
    return "<ul>" + "".join(f"<li>{h(item)}</li>" for item in values) + "</ul>"


def render_metadata(metadata: Any) -> str:
    if not isinstance(metadata, Mapping) or not metadata:
        return ""
    rows = "".join(
        f"<dt>{h(key)}</dt><dd>{h(value)}</dd>"
        for key, value in metadata.items()
    )
    return f'<section class="panel"><h2>Metadata</h2><dl class="metadata">{rows}</dl></section>'


def render_metrics(metrics: Any) -> str:
    cards = []
    for metric in list_of_mappings(metrics):
        label = h(metric.get("label", "Metric"))
        value = h(metric.get("value", ""))
        note = h(metric.get("note", ""))
        note_html = f'<span class="metric-note">{note}</span>' if note else ""
        cards.append(
            f'<article class="panel"><h3>{label}</h3>'
            f'<span class="metric-value">{value}</span>{note_html}</article>'
        )
    if not cards:
        return ""
    return f'<section><h2>Metrics</h2><div class="grid">{"".join(cards)}</div></section>'


def render_sections(sections: Any, title: str = "Sections") -> str:
    rendered = []
    for section in list_of_mappings(sections):
        heading = h(section.get("heading", "Section"))
        body = render_paragraphs(section.get("body", ""))
        items = render_items(section.get("items", []))
        rendered.append(
            f'<article class="panel"><h3>{heading}</h3>'
            f'<div class="section-body">{body}{items}</div></article>'
        )
    if not rendered:
        return ""
    return f'<section><h2>{h(title)}</h2>{"".join(rendered)}</section>'


def render_tables(tables: Any) -> str:
    rendered = []
    for table in list_of_mappings(tables):
        title = h(table.get("title", "Table"))
        columns = [h(column) for column in list_of_values(table.get("columns", []))]
        header = "".join(f"<th>{column}</th>" for column in columns)
        rows = []
        for row in list_of_values(table.get("rows", [])):
            cells = list_of_values(row)
            rows.append("<tr>" + "".join(f"<td>{h(cell)}</td>" for cell in cells) + "</tr>")
        rendered.append(
            f'<article class="panel"><h3>{title}</h3><table><thead><tr>{header}</tr>'
            f'</thead><tbody>{"".join(rows)}</tbody></table></article>'
        )
    if not rendered:
        return ""
    return f'<section><h2>Tables</h2>{"".join(rendered)}</section>'


def render_findings(findings: Any) -> str:
    rendered = []
    for finding in list_of_mappings(findings):
        severity = clean_text(finding.get("severity", "info")).lower()
        if severity not in {"info", "low", "medium", "high", "critical"}:
            severity = "info"
        rendered.append(
            '<article class="panel finding {severity}">'
            '<span class="severity">{severity}</span>'
            '<h3>{title}</h3>'
            '<div class="section-body">{body}</div>'
            '</article>'.format(
                severity=h(severity),
                title=h(finding.get("title", "Finding")),
                body=render_paragraphs(finding.get("body", "")),
            )
        )
    if not rendered:
        return ""
    return f'<section><h2>Findings</h2>{"".join(rendered)}</section>'


def render_links(links: Any) -> str:
    values = list_of_values(links)
    if not values:
        return ""
    items = []
    for link in values:
        if isinstance(link, Mapping):
            label = link.get("label", link.get("title", "Reference"))
            target = link.get("target", link.get("path", ""))
            text = f"{clean_text(label)}: {clean_text(target)}" if target else clean_text(label)
        else:
            text = clean_text(link)
        items.append(f'<li class="local-ref">{h(text)}</li>')
    return f'<section class="panel"><h2>References</h2><ul>{"".join(items)}</ul></section>'


def render_body(report: Mapping[str, Any]) -> str:
    title = h(report.get("title", "Untitled report"))
    subtitle = h(report.get("subtitle", ""))
    summary = render_paragraphs(report.get("summary", ""))
    subtitle_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""
    summary_html = f'<div class="summary">{summary}</div>' if summary else ""
    body_parts: Iterable[str] = (
        f'<main class="report"><header class="hero"><h1>{title}</h1>'
        f'{subtitle_html}{summary_html}</header>',
        render_metadata(report.get("metadata")),
        render_metrics(report.get("metrics")),
        render_sections(report.get("sections")),
        render_tables(report.get("tables")),
        render_findings(report.get("findings")),
        render_links(report.get("links")),
        render_sections(report.get("appendix"), title="Appendix"),
        "</main>",
    )
    return "".join(part for part in body_parts if part)


def render_html(report: Mapping[str, Any], template_path: Path = DEFAULT_TEMPLATE_PATH) -> str:
    template = template_path.read_text(encoding="utf-8")
    html = template.replace("__REPORT_TITLE__", h(report.get("title", "Untitled report")))
    html = html.replace("__REPORT_CSS__", REPORT_CSS)
    html = html.replace("__REPORT_BODY__", render_body(report))
    return html


def check_html_text(html: str) -> list[str]:
    issues: list[str] = []
    lowered = html.lower()
    for pattern in FORBIDDEN_HTML_SNIPPETS:
        if pattern.lower() in lowered:
            issues.append(f"forbidden pattern found: {pattern}")
    for regex, label in FORBIDDEN_HTML_REGEXES:
        if regex.search(html):
            issues.append(f"forbidden pattern found: {label}")
    if "connect-src 'none'" not in html:
        issues.append("missing Content Security Policy connect-src 'none'")
    return issues


def check_html(path: Path) -> list[str]:
    return check_html_text(path.read_text(encoding="utf-8"))


def write_html(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Generic report JSON input")
    parser.add_argument("--output", type=Path, help="HTML output path")
    parser.add_argument(
        "--check-html",
        type=Path,
        help="Validate an existing HTML file without rendering",
    )
    parser.add_argument("--validate", action="store_true", help="Validate output HTML after rendering")
    args = parser.parse_args(argv)

    if args.check_html:
        issues = check_html(args.check_html)
        if issues:
            for issue in issues:
                print(issue, file=sys.stderr)
            return 1
        return 0

    if not args.input or not args.output:
        parser.error("--input and --output are required unless --check-html is used")

    report = load_json(args.input)
    html = render_html(report)
    write_html(args.output, html)

    if args.validate:
        issues = check_html(args.output)
        if issues:
            for issue in issues:
                print(issue, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
