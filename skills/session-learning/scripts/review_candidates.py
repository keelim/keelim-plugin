#!/usr/bin/env python3
"""Review session-learning candidates and suggest promotion targets.

This script is intentionally read-only. It scans `.omx/learning/candidates`
files and prints deterministic routing recommendations; it does not edit
AGENTS.md, README.md, skills, docs, or global policy files.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROMOTION_SCOPES = {"project", "workspace", "user-global", "skill", "archive"}

TARGETS = {
    "project": "AGENTS.md",
    "workspace": "workspace AGENTS.md or docs/*",
    "user-global": "~/.codex/AGENTS.md",
    "skill": "skills/<name>/SKILL.md",
    "archive": ".omx/learning/archive/",
}


@dataclass(frozen=True)
class Candidate:
    path: Path
    frontmatter: dict[str, str]
    body: str


@dataclass(frozen=True)
class Recommendation:
    candidate: Candidate
    promotion_scope: str
    target: str
    reason: str


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    frontmatter: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip("'\"")
    return frontmatter, parts[2].lstrip()


def read_candidate(path: Path) -> Candidate:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    return Candidate(path=path, frontmatter=frontmatter, body=body)


def candidate_files(root: Path, since_days: int | None) -> list[Path]:
    candidate_dir = root / ".omx" / "learning" / "candidates"
    if not candidate_dir.is_dir():
        return []
    cutoff = None if since_days is None else time.time() - (since_days * 24 * 60 * 60)
    files = sorted(candidate_dir.glob("*.md"))
    if cutoff is None:
        return files
    return [path for path in files if path.stat().st_mtime >= cutoff]


def text_for_classification(candidate: Candidate) -> str:
    body = candidate.body.split("\n## Promotion Target", 1)[0]
    fields = [
        candidate.frontmatter.get("promotion_scope", ""),
        candidate.frontmatter.get("trigger", ""),
        candidate.frontmatter.get("applies_to", ""),
        candidate.frontmatter.get("recommended_target", ""),
        body,
    ]
    return "\n".join(fields).lower()


def classify(candidate: Candidate) -> tuple[str, str]:
    explicit_scope = candidate.frontmatter.get("promotion_scope", "").strip()
    if explicit_scope in PROMOTION_SCOPES and explicit_scope != "project":
        return explicit_scope, f"frontmatter promotion_scope={explicit_scope}"

    status = candidate.frontmatter.get("status", "").lower()
    target = candidate.frontmatter.get("target", "").lower()
    if status in {"archive", "archived"} or target == "archive":
        return "archive", "frontmatter marks it for archive"

    text = text_for_classification(candidate)
    if any(marker in text for marker in ("should archive", "too session-specific", "one-off only", "duplicate candidate")):
        return "archive", "candidate appears weak, duplicate, or session-specific"
    if any(marker in text for marker in ("reusable workflow", "repeatable workflow", "procedure", "skill.md", "turn this into a skill")):
        return "skill", "candidate describes a reusable procedure"
    if any(marker in text for marker in ("user-global", "all projects", "every project", "global policy", "~/.codex")):
        return "user-global", "candidate applies across projects"
    if any(marker in text for marker in ("workspace", "child repo", "root repo", "multi-repo", "repo boundary", "monorepo")):
        return "workspace", "candidate affects workspace or repo-boundary behavior"
    return "project", "candidate appears project-specific or needs local review"


def recommend(candidate: Candidate) -> Recommendation:
    scope, reason = classify(candidate)
    target = candidate.frontmatter.get("recommended_target", "")
    if not target or scope != candidate.frontmatter.get("promotion_scope", "project"):
        target = TARGETS[scope]
    return Recommendation(candidate=candidate, promotion_scope=scope, target=target, reason=reason)


def render_markdown(recommendations: list[Recommendation], roots: list[Path]) -> str:
    lines = [
        "# Session Learning Candidate Review",
        "",
        f"- Roots scanned: {', '.join(str(root) for root in roots)}",
        f"- Candidates found: {len(recommendations)}",
        "",
    ]
    if not recommendations:
        lines.append("No candidates found.")
        return "\n".join(lines) + "\n"

    lines.extend(["| Candidate | Promotion | Target | Reason |", "| --- | --- | --- | --- |"])
    for item in recommendations:
        path = str(item.candidate.path)
        lines.append(f"| `{path}` | `{item.promotion_scope}` | `{item.target}` | {item.reason} |")
    return "\n".join(lines) + "\n"


def render_json(recommendations: list[Recommendation], roots: list[Path]) -> str:
    payload: dict[str, Any] = {
        "roots": [str(root) for root in roots],
        "candidates": [
            {
                "path": str(item.candidate.path),
                "promotion_scope": item.promotion_scope,
                "target": item.target,
                "reason": item.reason,
            }
            for item in recommendations
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roots", nargs="+", default=["."], help="Project roots to scan.")
    parser.add_argument("--since-days", type=int, default=None, help="Only include candidates modified within N days.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roots = [Path(root).expanduser().resolve() for root in args.roots]
    recommendations: list[Recommendation] = []
    for root in roots:
        for path in candidate_files(root, args.since_days):
            recommendations.append(recommend(read_candidate(path)))

    if args.format == "json":
        print(render_json(recommendations, roots), end="")
    else:
        print(render_markdown(recommendations, roots), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
