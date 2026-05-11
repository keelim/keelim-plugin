#!/usr/bin/env python3
"""Project-local session learning observer.

This script is intentionally conservative: it records observations under
`.omx/learning` and never edits canonical project files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|credentials?|auth)"
    r"""(["'\s:=]+)"""
    r"([A-Za-z]+\s+)?"
    r"([-A-Za-z0-9_/.+=]{8,})"
)

SKIP_PATH_PARTS = ("observer-sessions", ".claude-mem", ".omx/learning")
PREVIEW_LIMIT = 2000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def slug_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def scrub(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    text = SECRET_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}{match.group(3) or ''}[REDACTED]", text)
    return text[:PREVIEW_LIMIT]


def load_payload(raw: str) -> tuple[dict[str, Any], str | None]:
    if not raw.strip():
        return {}, None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, f"json_decode_error: {exc}"
    if not isinstance(parsed, dict):
        return {}, "json_payload_is_not_object"
    return parsed, None


def first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def run_git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def root_from_cwd(cwd_text: str | None) -> Path:
    cwd = Path(cwd_text or os.getcwd()).expanduser()
    if not cwd.exists():
        cwd = Path(os.getcwd())
    cwd = cwd.resolve()

    git_root = run_git(["rev-parse", "--show-toplevel"], cwd)
    if git_root:
        return Path(git_root).resolve()
    return cwd


def detect_project_root(cwd_text: str | None) -> Path:
    env_root = os.environ.get("SESSION_LEARNING_PROJECT_DIR")
    if env_root and Path(env_root).is_dir():
        return Path(env_root).resolve()
    return root_from_cwd(cwd_text)


def project_id(root: Path) -> str:
    remote = run_git(["remote", "get-url", "origin"], root)
    source = remote or str(root)
    source = re.sub(r"://[^@]+@", "://", source)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


def path_contains(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def scope_root() -> Path | None:
    scope = os.environ.get("SESSION_LEARNING_SCOPE_ROOT")
    if not scope:
        return None
    path = Path(scope).expanduser()
    if not path.is_dir():
        return None
    return path.resolve()


def should_skip(payload: dict[str, Any], root: Path, cwd_text: str | None, event_root: Path) -> bool:
    if os.environ.get("SESSION_LEARNING_DISABLED") == "1":
        return True
    if os.environ.get("ECC_SKIP_OBSERVE") == "1":
        return True
    if payload.get("agent_id"):
        return True
    scope = scope_root()
    if os.environ.get("SESSION_LEARNING_SCOPE_ROOT") and scope is None:
        return True
    if scope is not None:
        candidates = [event_root]
        if cwd_text:
            cwd_path = Path(cwd_text).expanduser()
            if cwd_path.exists():
                candidates.append(cwd_path.resolve())
        if not any(path_contains(candidate, scope) for candidate in candidates):
            return True
    combined = f"{cwd_text or ''} {root}"
    return any(part in combined for part in SKIP_PATH_PARTS)


def learning_dirs(root: Path) -> dict[str, Path]:
    base = root / ".omx" / "learning"
    paths = {
        "base": base,
        "observations": base / "observations.jsonl",
        "candidates": base / "candidates",
        "promoted": base / "promoted",
        "archive": base / "archive",
    }
    for key, path in paths.items():
        if key != "observations":
            path.mkdir(parents=True, exist_ok=True)
    return paths


def build_observation(phase: str, payload: dict[str, Any], raw_error: str | None, root: Path) -> dict[str, Any]:
    cwd_text = first_present(payload, ("cwd", "working_directory", "workdir"))
    tool_input = first_present(payload, ("tool_input", "input", "arguments", "params", "prompt", "user_prompt"))
    tool_output = first_present(payload, ("tool_response", "tool_output", "output", "result", "error"))
    observation: dict[str, Any] = {
        "timestamp": utc_now(),
        "source": os.environ.get("SESSION_LEARNING_SOURCE", "codex-or-claude"),
        "phase": phase,
        "session_id": str(first_present(payload, ("session_id", "conversation_id", "thread_id")) or "unknown"),
        "tool_use_id": str(first_present(payload, ("tool_use_id", "call_id")) or ""),
        "cwd": str(cwd_text or ""),
        "project_root": str(root),
        "project_id": project_id(root),
        "tool": str(first_present(payload, ("tool_name", "tool", "name")) or "unknown"),
        "redacted": True,
    }
    if raw_error:
        observation["outcome_signal"] = "parse_error"
        observation["output_preview"] = scrub(raw_error)
    else:
        input_preview = scrub(tool_input)
        output_preview = scrub(tool_output)
        if input_preview:
            observation["input_preview"] = input_preview
        if output_preview:
            observation["output_preview"] = output_preview
        observation["outcome_signal"] = infer_outcome(phase, observation)
    return observation


def infer_outcome(phase: str, observation: dict[str, Any]) -> str:
    text = f"{observation.get('input_preview', '')}\n{observation.get('output_preview', '')}".lower()
    if phase in {"stop", "pre-compact", "post-compact"}:
        return phase
    if any(marker in text for marker in ("traceback", "error", "failed", "exception", "permission denied")):
        return "error-signal"
    if any(marker in text for marker in ("pass", "success", "approved", "complete", "exit code 0")):
        return "success-signal"
    if any(marker in text for marker in ("actually", "instead", "always", "next time", "don't", "do not")):
        return "correction-or-preference-signal"
    return "observed"


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def recent_session_observations(path: Path, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("session_id") == session_id:
                rows.append(row)
    return rows[-limit:]


def write_stop_candidate(paths: dict[str, Path], observation: dict[str, Any]) -> Path:
    session_id = observation.get("session_id", "unknown")
    safe_session = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(session_id))[:48] or "unknown"
    candidate_path = paths["candidates"] / f"{slug_timestamp()}-{safe_session}.md"
    recent = recent_session_observations(paths["observations"], str(session_id))
    signals: dict[str, int] = {}
    for item in recent:
        signal = str(item.get("outcome_signal", "observed"))
        signals[signal] = signals.get(signal, 0) + 1

    body = [
        "---",
        f"id: {candidate_path.stem}",
        f"created_at: {utc_now()}",
        f"project: {observation.get('project_id', 'unknown')}",
        "confidence: 0.3",
        "scope: project",
        "promotion_scope: project",
        "trigger: review-required",
        "applies_to: active-project",
        "evidence_level: low",
        "recommended_target: AGENTS.md",
        "target: review",
        "status: candidate",
        f"source_sessions: {json.dumps([session_id])}",
        f"source_projects: {json.dumps([observation.get('project_id', 'unknown')])}",
        "---",
        "",
        "# Session Learning Candidate",
        "",
        "## Evidence Summary",
        f"- Session: `{session_id}`",
        f"- Project root: `{observation.get('project_root', '')}`",
        f"- Observations in this session: {len(recent)}",
        f"- Signals: {json.dumps(signals, sort_keys=True)}",
        "",
        "## Review Prompt",
        "Decide whether this session produced a durable lesson. Promote only if there is a concrete future trigger and clear evidence.",
        "",
        "## Promotion Target",
        "- `project`: project-specific instructions, inventory, commands, routes, schemas, or docs.",
        "- `workspace`: root or multi-repo coordination rules.",
        "- `user-global`: durable personal preferences or policy that should apply across projects.",
        "- `skill`: reusable procedural workflow with a clear trigger.",
        "- `archive`: weak, duplicate, stale, or session-specific.",
        "",
    ]
    candidate_path.write_text("\n".join(body), encoding="utf-8")
    return candidate_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="post")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    raw = sys.stdin.read()
    payload, raw_error = load_payload(raw)
    cwd_text = first_present(payload, ("cwd", "working_directory", "workdir"))
    event_root = root_from_cwd(str(cwd_text) if cwd_text else None)
    root = detect_project_root(str(cwd_text) if cwd_text else None)
    scope = scope_root()
    if scope is not None:
        root = scope
    if should_skip(payload, root, str(cwd_text) if cwd_text else None, event_root):
        return 0

    paths = learning_dirs(root)
    observation = build_observation(args.phase, payload, raw_error, root)
    if args.dry_run:
        print(json.dumps(observation, ensure_ascii=False, sort_keys=True))
        return 0

    append_jsonl(paths["observations"], observation)
    if args.phase == "stop":
        candidate_path = write_stop_candidate(paths, observation)
        print(f"[session-learning] wrote {candidate_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
