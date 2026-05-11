#!/usr/bin/env python3
"""Build an offline session usage dashboard for Codex and Claude JSONL logs."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


SKILL_RE = re.compile(r"\[\$([A-Za-z0-9:_-]+)\]|\$([A-Za-z][A-Za-z0-9:_-]+)")
ENV_LIKE = {
    "HOME",
    "PATH",
    "PWD",
    "SHELL",
    "USER",
    "TMPDIR",
}
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|credential)([=:]\s*)([^,\s\"']+)"
)
OFFLINE_FORBIDDEN = (
    "http://",
    "https://",
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
    "EventSource",
    "sendBeacon",
    "<script src=",
    "<link rel=\"stylesheet\"",
    "<iframe",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_slug() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_text(value: Any, limit: int = 160) -> str:
    text = "" if value is None else str(value)
    text = SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
    text = text.replace("\x00", "")
    if len(text) > limit:
        text = text[: limit - 1] + "..."
    return text


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                records.append({"_parse_warning": f"{path}:{line_no}: invalid json"})
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def h(value: Any, limit: int = 160) -> str:
    return html.escape(safe_text(value, limit), quote=True)


class UsageCollector:
    def __init__(self) -> None:
        self.generated_at = utc_now()
        self.input_files: list[dict[str, str]] = []
        self.tools: Counter[tuple[str, str]] = Counter()
        self.skills: Counter[tuple[str, str]] = Counter()
        self.subagents: Counter[tuple[str, str]] = Counter()
        self.events: list[dict[str, str]] = []
        self.warnings: list[str] = []
        self.sessions: set[str] = set()
        self.provider_event_counts: Counter[str] = Counter()

    def add_input(self, provider: str, path: Path) -> None:
        self.input_files.append({"provider": provider, "path": str(path)})

    def add_event(self, provider: str, kind: str, name: str, timestamp: str | None = None) -> None:
        name = safe_text(name, 120)
        if not name:
            return
        self.provider_event_counts[provider] += 1
        if kind == "tool":
            self.tools[(provider, name)] += 1
        elif kind == "skill":
            self.skills[(provider, name)] += 1
        elif kind == "subagent":
            self.subagents[(provider, name)] += 1
        self.events.append(
            {
                "timestamp": safe_text(timestamp or "", 40),
                "provider": provider,
                "kind": kind,
                "name": name,
            }
        )

    def warning(self, message: str) -> None:
        self.warnings.append(safe_text(message, 220))


def extract_text_parts(content: Any) -> list[str]:
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return parts


def count_skill_mentions(collector: UsageCollector, provider: str, content: Any, timestamp: str | None) -> None:
    for text in extract_text_parts(content):
        for match in SKILL_RE.finditer(text):
            name = match.group(1) or match.group(2)
            if not name or name in ENV_LIKE or name.isupper():
                continue
            collector.add_event(provider, "skill", name, timestamp)


def parse_codex(path: Path, collector: UsageCollector) -> None:
    collector.add_input("codex", path)
    for record in read_jsonl(path):
        if "_parse_warning" in record:
            collector.warning(record["_parse_warning"])
            continue
        timestamp = record.get("timestamp")
        payload = record.get("payload")
        if record.get("type") == "session_meta" and isinstance(payload, dict):
            session_id = payload.get("id")
            if session_id:
                collector.sessions.add(f"codex:{session_id}")
            thread_source = payload.get("thread_source")
            source = payload.get("source")
            if thread_source == "subagent":
                label = "subagent"
                if isinstance(source, dict) and isinstance(source.get("subagent"), dict):
                    subagent_info = source["subagent"]
                    label = next((safe_text(v) for v in subagent_info.values() if v), label)
                collector.add_event("codex", "subagent", label, timestamp)
            continue
        if not isinstance(payload, dict):
            continue
        payload_type = payload.get("type")
        if payload_type == "function_call":
            collector.add_event("codex", "tool", payload.get("name") or "function_call", timestamp)
        elif payload_type == "custom_tool_call":
            collector.add_event("codex", "tool", payload.get("name") or "custom_tool_call", timestamp)
        elif payload_type == "web_search_call":
            collector.add_event("codex", "tool", "web_search", timestamp)
        elif payload_type == "message" and payload.get("role") == "user":
            count_skill_mentions(collector, "codex", payload.get("content"), timestamp)


def parse_claude(path: Path, collector: UsageCollector) -> None:
    collector.add_input("claude", path)
    for record in read_jsonl(path):
        if "_parse_warning" in record:
            collector.warning(record["_parse_warning"])
            continue
        timestamp = record.get("timestamp")
        session_id = record.get("sessionId")
        if session_id:
            collector.sessions.add(f"claude:{session_id}")
        attribution_skill = record.get("attributionSkill")
        if attribution_skill:
            collector.add_event("claude", "skill", attribution_skill, timestamp)
        attribution_agent = record.get("attributionAgent")
        if attribution_agent:
            collector.add_event("claude", "subagent", attribution_agent, timestamp)
        if record.get("isSidechain") is True:
            collector.add_event("claude", "subagent", "sidechain", timestamp)
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if message.get("role") == "user":
            count_skill_mentions(collector, "claude", content, timestamp)
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            tool_name = item.get("name") or "tool_use"
            collector.add_event("claude", "tool", tool_name, timestamp)
            if tool_name == "Agent":
                tool_input = item.get("input")
                if isinstance(tool_input, dict):
                    subagent_type = tool_input.get("subagent_type") or tool_input.get("agent_type")
                    if subagent_type:
                        collector.add_event("claude", "subagent", subagent_type, timestamp)


def project_slug(cwd: Path) -> str:
    return str(cwd.resolve()).replace("/", "-")


def newest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def codex_meta_cwd(path: Path) -> str | None:
    try:
        for record in read_jsonl(path):
            payload = record.get("payload")
            if record.get("type") == "session_meta" and isinstance(payload, dict):
                cwd = payload.get("cwd")
                return str(cwd) if cwd else None
    except OSError:
        return None
    return None


def find_current_codex(cwd: Path) -> list[Path]:
    root = Path.home() / ".codex" / "sessions"
    if not root.is_dir():
        return []
    candidates = sorted(root.glob("*/*/*/*.jsonl"))
    matching = [path for path in candidates if codex_meta_cwd(path) == str(cwd.resolve())]
    pick = newest(matching) or newest(candidates)
    return [pick] if pick else []


def find_current_claude(cwd: Path) -> list[Path]:
    project_dir = Path.home() / ".claude" / "projects" / project_slug(cwd)
    if not project_dir.is_dir():
        return []
    top_level = [path for path in project_dir.glob("*.jsonl") if path.is_file()]
    main = newest(top_level)
    if not main:
        return []
    result = [main]
    subagents = main.with_suffix("")
    subagent_dir = subagents / "subagents"
    if subagent_dir.is_dir():
        result.extend(sorted(subagent_dir.glob("*.jsonl")))
    return result


def rows(counter: Counter[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        {"provider": provider, "name": name, "count": count}
        for (provider, name), count in sorted(counter.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    ]


def top_rows_html(title: str, items: list[dict[str, Any]]) -> str:
    max_count = max((item["count"] for item in items), default=1)
    body = []
    for item in items[:24]:
        width = max(4, round((item["count"] / max_count) * 100))
        body.append(
            "<tr>"
            f"<td><span class=\"provider\">{h(item['provider'])}</span></td>"
            f"<td>{h(item['name'])}</td>"
            f"<td class=\"count\">{item['count']}</td>"
            f"<td><span class=\"bar\"><span style=\"width:{width}%\"></span></span></td>"
            "</tr>"
        )
    if not body:
        body.append("<tr><td colspan=\"4\" class=\"empty\">No events found.</td></tr>")
    return (
        "<section class=\"panel\">"
        f"<h2>{h(title)}</h2>"
        "<table><thead><tr><th>Runtime</th><th>Name</th><th>Count</th><th>Share</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
        "</section>"
    )


def timeline_html(events: list[dict[str, str]]) -> str:
    if not events:
        return "<p class=\"empty\">No timeline events found.</p>"
    items = []
    for event in events[-80:]:
        items.append(
            "<li>"
            f"<span>{h(event.get('timestamp')) or 'no timestamp'}</span>"
            f"<strong>{h(event.get('provider'))}</strong>"
            f"<em>{h(event.get('kind'))}</em>"
            f"{h(event.get('name'))}"
            "</li>"
        )
    return f"<ol class=\"timeline\">{''.join(items)}</ol>"


def build_summary(collector: UsageCollector) -> dict[str, Any]:
    tool_rows = rows(collector.tools)
    skill_rows = rows(collector.skills)
    subagent_rows = rows(collector.subagents)
    return {
        "generated_at": collector.generated_at,
        "inputs": collector.input_files,
        "totals": {
            "sessions": len(collector.sessions),
            "events": len(collector.events),
            "tool_events": sum(item["count"] for item in tool_rows),
            "skill_events": sum(item["count"] for item in skill_rows),
            "subagent_events": sum(item["count"] for item in subagent_rows),
            "unique_tools": len(tool_rows),
            "unique_skills": len(skill_rows),
            "unique_subagents": len(subagent_rows),
        },
        "providers": dict(sorted(collector.provider_event_counts.items())),
        "tools": tool_rows,
        "skills": skill_rows,
        "subagents": subagent_rows,
        "timeline": collector.events[-200:],
        "warnings": collector.warnings,
    }


def render_html(summary: dict[str, Any]) -> str:
    totals = summary["totals"]
    inputs = summary["inputs"]
    warnings = summary["warnings"]
    kpis = [
        ("Events", totals["events"]),
        ("Tools", totals["unique_tools"]),
        ("Skills", totals["unique_skills"]),
        ("Subagents", totals["unique_subagents"]),
    ]
    kpi_html = "".join(f"<div class=\"kpi\"><span>{h(label)}</span><strong>{value}</strong></div>" for label, value in kpis)
    inputs_html = "".join(
        f"<li><span>{h(item['provider'])}</span>{h(item['path'], 220)}</li>" for item in inputs
    ) or "<li><span>none</span>No input files found.</li>"
    warning_html = "".join(f"<li>{h(warning)}</li>" for warning in warnings) or "<li>No parser warnings.</li>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
  <title>Session Usage Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #17181c;
      --muted: #626976;
      --line: #dce1e8;
      --panel: #ffffff;
      --accent: #126b59;
      --accent-2: #2a5caa;
      --soft: #eef7f4;
      --shadow: 0 18px 45px rgba(22, 28, 36, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    main {{ width: min(1180px, calc(100vw - 32px)); margin: 0 auto; padding: 32px 0 48px; }}
    header {{ display: grid; gap: 14px; margin-bottom: 24px; }}
    h1 {{ margin: 0; font-size: clamp(28px, 4vw, 46px); letter-spacing: 0; }}
    h2 {{ margin: 0 0 16px; font-size: 18px; letter-spacing: 0; }}
    p {{ margin: 0; color: var(--muted); max-width: 780px; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 13px; }}
    .pill {{ border: 1px solid var(--line); background: var(--panel); border-radius: 999px; padding: 6px 10px; }}
    .kpis {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 22px 0; }}
    .kpi, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .kpi {{ padding: 18px; min-height: 108px; display: grid; align-content: space-between; }}
    .kpi span {{ color: var(--muted); font-size: 13px; }}
    .kpi strong {{ font-size: 34px; letter-spacing: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
    .panel {{ padding: 18px; overflow: hidden; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th {{ color: var(--muted); text-align: left; font-weight: 650; border-bottom: 1px solid var(--line); padding: 8px; }}
    td {{ border-bottom: 1px solid #edf0f4; padding: 10px 8px; vertical-align: middle; }}
    tr:last-child td {{ border-bottom: 0; }}
    .provider {{ display: inline-flex; min-width: 64px; justify-content: center; border-radius: 999px; background: var(--soft); color: var(--accent); padding: 4px 8px; font-size: 12px; font-weight: 700; }}
    .count {{ font-variant-numeric: tabular-nums; font-weight: 750; }}
    .bar {{ display: block; height: 8px; border-radius: 999px; background: #edf0f4; overflow: hidden; min-width: 84px; }}
    .bar span {{ display: block; height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent-2)); }}
    .lists {{ display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 14px; margin-top: 14px; }}
    ul, ol {{ margin: 0; padding: 0; list-style: none; }}
    .inputs li, .warnings li {{ display: grid; grid-template-columns: 92px 1fr; gap: 10px; padding: 9px 0; border-bottom: 1px solid #edf0f4; color: var(--muted); font-size: 13px; word-break: break-word; }}
    .inputs li:last-child, .warnings li:last-child {{ border-bottom: 0; }}
    .inputs span {{ color: var(--ink); font-weight: 750; }}
    .timeline {{ display: grid; gap: 8px; max-height: 420px; overflow: auto; padding-right: 4px; }}
    .timeline li {{ display: grid; grid-template-columns: minmax(120px, 0.9fr) 70px 80px 1fr; gap: 8px; align-items: center; border: 1px solid #edf0f4; border-radius: 8px; padding: 9px; font-size: 13px; }}
    .timeline span {{ color: var(--muted); }}
    .timeline strong, .timeline em {{ font-style: normal; font-weight: 750; }}
    .timeline em {{ color: var(--accent); }}
    .empty {{ color: var(--muted); font-size: 13px; padding: 12px 0; }}
    @media (max-width: 860px) {{
      main {{ width: min(100vw - 24px, 1180px); padding-top: 22px; }}
      .kpis, .grid, .lists {{ grid-template-columns: 1fr; }}
      .timeline li {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="meta">
        <span class="pill">Generated {h(summary['generated_at'])}</span>
        <span class="pill">{totals['sessions']} sessions</span>
        <span class="pill">{len(inputs)} input files</span>
      </div>
      <h1>Session Usage Dashboard</h1>
      <p>Offline usage summary for agent tools, invoked skills, and subagents. Raw prompts, arguments, and outputs are intentionally excluded.</p>
    </header>
    <section class="kpis">{kpi_html}</section>
    <section class="grid">
      {top_rows_html("Tool Usage", summary["tools"])}
      {top_rows_html("Skill Invocations", summary["skills"])}
      {top_rows_html("Subagent Activity", summary["subagents"])}
      <section class="panel">
        <h2>Recent Sanitized Events</h2>
        {timeline_html(summary["timeline"])}
      </section>
    </section>
    <section class="lists">
      <section class="panel">
        <h2>Inputs</h2>
        <ul class="inputs">{inputs_html}</ul>
      </section>
      <section class="panel">
        <h2>Warnings</h2>
        <ul class="warnings">{warning_html}</ul>
      </section>
    </section>
  </main>
</body>
</html>
"""


def validate_offline_html(text: str) -> list[str]:
    lower = text.lower()
    failures = []
    for marker in OFFLINE_FORBIDDEN:
        if marker.lower() in lower:
            failures.append(f"forbidden marker present: {marker}")
    return failures


def write_outputs(summary: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.json"
    html_path = out_dir / "dashboard.html"
    html_text = render_html(summary)
    failures = validate_offline_html(html_text)
    if failures:
        raise SystemExit("; ".join(failures))
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    return summary_path, html_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an offline Codex/Claude session usage dashboard.")
    parser.add_argument("--current", action="store_true", help="Auto-detect the latest session logs for --cwd.")
    parser.add_argument("--cwd", default=os.getcwd(), help="Project cwd used for current-session discovery.")
    parser.add_argument("--codex-session", action="append", default=[], help="Path to a Codex session JSONL file.")
    parser.add_argument("--claude-session", action="append", default=[], help="Path to a Claude session JSONL file.")
    parser.add_argument("--out", help="Output directory. Defaults to .omx/session-usage/<timestamp>.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cwd = Path(args.cwd).expanduser().resolve()
    codex_paths = [Path(path).expanduser() for path in args.codex_session]
    claude_paths = [Path(path).expanduser() for path in args.claude_session]
    if args.current or (not codex_paths and not claude_paths):
        codex_paths.extend(path for path in find_current_codex(cwd) if path not in codex_paths)
        claude_paths.extend(path for path in find_current_claude(cwd) if path not in claude_paths)
    collector = UsageCollector()
    for path in codex_paths:
        if path.is_file():
            parse_codex(path, collector)
        else:
            collector.warning(f"missing codex session: {path}")
    for path in claude_paths:
        if path.is_file():
            parse_claude(path, collector)
        else:
            collector.warning(f"missing claude session: {path}")
    if not collector.input_files:
        collector.warning("no input files were discovered; pass --codex-session or --claude-session explicitly")
    summary = build_summary(collector)
    out_dir = Path(args.out).expanduser() if args.out else Path(".omx") / "session-usage" / timestamp_slug()
    summary_path, html_path = write_outputs(summary, out_dir)
    print(f"summary: {summary_path}")
    print(f"html: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
