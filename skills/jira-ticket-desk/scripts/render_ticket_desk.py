#!/usr/bin/env python3
"""Build ticket desk JSON and inject it into the offline HTML template."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_PATH = SKILL_ROOT / "assets" / "ticket-desk-template.html"
DATA_PLACEHOLDER = "__TICKET_DESK_DATA__"

BUCKETS = {
    "focus": "Focus",
    "next": "Next",
    "waiting": "Waiting",
    "blocked": "Blocked",
    "monitoring": "Monitoring",
    "ignored": "Intentionally Ignored",
}

FORBIDDEN_HTML_PATTERNS = (
    "http://",
    "https://",
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
    "script src",
    "link href",
    "@import",
)

REMOTE_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pick(mapping: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return str(value)
    return default


def strip_remote_urls(value: Any) -> Any:
    if isinstance(value, str):
        return REMOTE_URL_RE.sub("[remote-url-omitted]", value)
    if isinstance(value, list):
        return [strip_remote_urls(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): strip_remote_urls(item) for key, item in value.items()}
    return value


def nested_name(value: Any) -> str:
    if isinstance(value, Mapping):
        return pick(value, "displayName", "name", "value")
    if value is None:
        return ""
    return str(value)


def extract_issues(payload: Any) -> List[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        issues = payload.get("issues")
        if isinstance(issues, list):
            return [item for item in issues if isinstance(item, Mapping)]
        values = payload.get("values")
        if isinstance(values, list):
            return [item for item in values if isinstance(item, Mapping)]
    raise ValueError("tickets JSON must be a Jira search object with issues, values, or a plain array")


def normalize_issue(issue: Mapping[str, Any]) -> Dict[str, Any]:
    fields = issue.get("fields") if isinstance(issue.get("fields"), Mapping) else {}
    status = fields.get("status", issue.get("status"))
    priority = fields.get("priority", issue.get("priority"))
    assignee = fields.get("assignee", issue.get("assignee"))
    issue_type = fields.get("issuetype", issue.get("issue_type", issue.get("issuetype")))
    project = fields.get("project", issue.get("project"))
    labels = fields.get("labels", issue.get("labels", []))

    if not isinstance(labels, list):
        labels = [str(labels)]

    return {
        "key": pick(issue, "key", "id", default="UNKNOWN"),
        "summary": pick(fields, "summary", default=pick(issue, "summary", "title", default="Untitled ticket")),
        "status": nested_name(status),
        "assignee": nested_name(assignee) or "Unassigned",
        "priority": nested_name(priority) or "None",
        "due": pick(fields, "duedate", "due", default=pick(issue, "due", "duedate")),
        "updated": pick(fields, "updated", default=pick(issue, "updated")),
        "project": nested_name(project),
        "issue_type": nested_name(issue_type),
        "labels": [str(label) for label in labels],
        "bucket": pick(issue, "bucket").lower(),
    }


def load_rules(path: Optional[Path]) -> Dict[str, Dict[str, str]]:
    if path is None:
        return {}
    return load_rules_from_object(load_json(path))


def load_rules_from_object(payload: Any) -> Dict[str, Dict[str, str]]:
    if not isinstance(payload, Mapping):
        raise ValueError("rules JSON must be an object")
    rules = payload.get("tickets", payload)
    if not isinstance(rules, Mapping):
        raise ValueError("rules JSON tickets must be an object")
    normalized: Dict[str, Dict[str, str]] = {}
    for key, value in rules.items():
        if isinstance(value, Mapping):
            normalized[str(key)] = {str(k): str(v) for k, v in value.items() if v is not None}
    return normalized


def classify(ticket: Mapping[str, Any], rule: Mapping[str, str]) -> str:
    requested = rule.get("bucket") or str(ticket.get("bucket") or "")
    requested = requested.lower().strip()
    if requested in BUCKETS:
        return requested

    text = " ".join(str(ticket.get(field, "")) for field in ("status", "priority", "summary")).lower()
    if "block" in text:
        return "blocked"
    if "wait" in text or "hold" in text or "review" in text:
        return "waiting"
    if "progress" in text or "critical" in text or "highest" in text:
        return "focus"
    return "next"


def enrich_tickets(issues: Iterable[Mapping[str, Any]], rules: Mapping[str, Mapping[str, str]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for issue in issues:
        ticket = normalize_issue(issue)
        rule = rules.get(str(ticket["key"]), {})
        ticket["bucket"] = classify(ticket, rule)
        ticket["reason"] = rule.get("reason", "")
        ticket["review_after"] = rule.get("review_after", "")
        ticket["note"] = rule.get("note", "")
        enriched.append(strip_remote_urls(ticket))
    return enriched


def build_desk_data(issues: Iterable[Mapping[str, Any]], rules: Mapping[str, Mapping[str, str]]) -> Dict[str, Any]:
    tickets = enrich_tickets(issues, rules)
    buckets = [{"id": bucket_id, "title": title} for bucket_id, title in BUCKETS.items()]
    counts = {bucket_id: 0 for bucket_id in BUCKETS}
    for ticket in tickets:
        counts[str(ticket.get("bucket", "next"))] = counts.get(str(ticket.get("bucket", "next")), 0) + 1
    return {
        "title": "Jira Ticket Desk",
        "subtitle": "Read-only local view for ticket triage.",
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "buckets": buckets,
        "counts": counts,
        "tickets": tickets,
    }


def normalize_desk_data(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("desk data JSON must be an object")
    tickets = payload.get("tickets")
    if not isinstance(tickets, list):
        raise ValueError("desk data JSON must contain a tickets array")
    data = dict(payload)
    data.setdefault("title", "Jira Ticket Desk")
    data.setdefault("subtitle", "Read-only local view for ticket triage.")
    data.setdefault("generated_at", dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    data.setdefault("buckets", [{"id": bucket_id, "title": title} for bucket_id, title in BUCKETS.items()])
    return strip_remote_urls(data)


def json_for_template(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return (
        encoded
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("</", "<\\/")
    )


def render_html(data: Mapping[str, Any], template_path: Path = DEFAULT_TEMPLATE_PATH) -> str:
    template = template_path.read_text(encoding="utf-8")
    if DATA_PLACEHOLDER not in template:
        raise ValueError(f"template is missing {DATA_PLACEHOLDER}")
    return template.replace(DATA_PLACEHOLDER, json_for_template(data))


def demo_payload() -> List[Dict[str, Any]]:
    return [
        {
            "key": "APP-101",
            "summary": "Stabilize weekly ticket desk flow",
            "status": "In Progress",
            "assignee": "Keelim",
            "priority": "Highest",
            "due": "2026-05-12",
            "updated": "2026-05-10",
            "labels": ["desk", "planning"],
        },
        {
            "key": "APP-205",
            "summary": "Wait for design approval",
            "status": "Waiting",
            "assignee": "Design",
            "priority": "Medium",
            "updated": "2026-05-09",
            "labels": ["dependency"],
        },
        {
            "key": "APP-404",
            "summary": "Legacy cleanup owned by another team",
            "status": "Open",
            "assignee": "Platform",
            "priority": "Low",
            "updated": "2026-05-01",
            "labels": ["legacy"],
            "bucket": "ignored",
        },
    ]


def check_html(path: Path) -> List[str]:
    content = path.read_text(encoding="utf-8")
    lowered = content.lower()
    failures = []
    for pattern in FORBIDDEN_HTML_PATTERNS:
        if pattern.lower() in lowered:
            failures.append(pattern)
    return failures


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickets", type=Path, help="Jira JSON file or normalized ticket JSON file")
    parser.add_argument("--rules", type=Path, help="Local ticket-desk rules JSON file")
    parser.add_argument("--data", type=Path, help="Prebuilt ticket desk data JSON to inject into the template")
    parser.add_argument("--data-output", type=Path, help="Write reusable ticket desk data JSON")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE_PATH, help="Offline HTML template path")
    parser.add_argument("--output", type=Path, help="Output HTML file")
    parser.add_argument("--demo", action="store_true", help="Render built-in demo tickets")
    parser.add_argument("--check-html", type=Path, help="Validate an existing HTML file for offline constraints")
    args = parser.parse_args(argv)

    if args.check_html:
        failures = check_html(args.check_html)
        if failures:
            print("Offline check failed: " + ", ".join(failures), file=sys.stderr)
            return 1
        print(f"Offline check passed: {args.check_html}")
        return 0

    if args.data:
        desk_data = normalize_desk_data(load_json(args.data))
    elif args.demo:
        desk_data = build_desk_data(demo_payload(), {})
    elif args.tickets:
        desk_data = build_desk_data(extract_issues(load_json(args.tickets)), load_rules(args.rules))
    else:
        parser.error("provide --data, --tickets, or --demo")

    if args.data_output:
        write_json(args.data_output, desk_data)
        print(f"Wrote data {args.data_output} with {len(desk_data.get('tickets', []))} tickets")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_html(desk_data, args.template), encoding="utf-8")
        failures = check_html(args.output)
        if failures:
            print("Generated HTML failed offline check: " + ", ".join(failures), file=sys.stderr)
            return 1
        print(f"Wrote {args.output} with {len(desk_data.get('tickets', []))} tickets")

    if not args.output and not args.data_output:
        parser.error("provide --output or --data-output")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
