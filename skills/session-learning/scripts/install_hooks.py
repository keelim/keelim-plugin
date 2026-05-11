#!/usr/bin/env python3
"""Install Session Learning hooks for Codex and Claude."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVENTS = (
    ("UserPromptSubmit", "prompt", 10),
    ("PreToolUse", "pre", 10),
    ("PostToolUse", "post", 10),
    ("Stop", "stop", 30),
    ("PreCompact", "pre-compact", 10),
    ("PostCompact", "post-compact", 10),
)


@dataclass(frozen=True)
class HookTarget:
    name: str
    path: Path


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def detect_project_root(path_text: str | None) -> Path:
    cwd = Path(path_text or os.getcwd()).expanduser().resolve()
    git_root = run_git(["rev-parse", "--show-toplevel"], cwd)
    if git_root:
        return Path(git_root).resolve()
    return cwd


def project_id(root: Path) -> str:
    remote = run_git(["remote", "get-url", "origin"], root)
    source = re.sub(r"://[^@]+@", "://", remote) if remote else str(root)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


def skill_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def default_codex_hooks_path() -> Path:
    return Path.home() / ".codex" / "hooks.json"


def default_claude_hooks_path() -> Path:
    return Path.home() / ".claude" / "hooks" / "hooks.json"


def hook_marker(phase: str, pid: str) -> str:
    return f"session-learning:{phase}:{pid}"


def hook_command(skill_root: Path, scope_root: Path | None, phase: str, pid: str, source: str) -> str:
    observe = skill_root / "hooks" / "observe.sh"
    parts = [
        "env",
        f"SESSION_LEARNING_SOURCE={source}",
        f"SESSION_LEARNING_HOOK_ID={hook_marker(phase, pid)}",
        f"SESSION_LEARNING_SCOPE={'global' if scope_root is None else 'project'}",
        "/bin/bash",
        str(observe),
        phase,
    ]
    if scope_root is not None:
        parts.insert(1, f"SESSION_LEARNING_SCOPE_ROOT={scope_root}")
    return " ".join(shlex.quote(part) for part in parts)


def command_has_marker(entry: Any, pid: str) -> bool:
    if not isinstance(entry, dict):
        return False
    entry_id = entry.get("id")
    if isinstance(entry_id, str) and entry_id.startswith("session-learning:") and entry_id.endswith(f":{pid}"):
        return True
    for hook in entry.get("hooks", []):
        command = hook.get("command") if isinstance(hook, dict) else None
        if isinstance(command, str) and "SESSION_LEARNING_HOOK_ID=session-learning:" in command and f":{pid}" in command:
            return True
    return False


def entry_commands(entry: Any) -> list[str]:
    if not isinstance(entry, dict):
        return []
    commands: list[str] = []
    for hook in entry.get("hooks", []):
        command = hook.get("command") if isinstance(hook, dict) else None
        if isinstance(command, str):
            commands.append(command)
    return commands


def load_config(path: Path, target: str) -> dict[str, Any]:
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} must contain a JSON object")
            return payload
    if target == "claude":
        return {"$schema": "https://json.schemastore.org/claude-code-settings.json", "hooks": {}}
    return {"hooks": {}}


def dump_config(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def write_config(path: Path, payload: dict[str, Any], dry_run: bool) -> str | None:
    if dry_run:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: str | None = None
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-{utc_stamp()}")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        backup_path = str(backup)
    content = dump_config(payload)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        tmp_name = handle.name
    os.replace(tmp_name, path)
    return backup_path


def target_entry(
    target: str,
    event: str,
    phase: str,
    timeout: int,
    skill_root: Path,
    scope_root: Path | None,
    pid: str,
) -> dict[str, Any]:
    command = hook_command(skill_root, scope_root, phase, pid, target)
    command_hook: dict[str, Any] = {"type": "command", "command": command, "timeout": timeout}
    if target == "claude" and event in {"UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "PostCompact"}:
        command_hook["async"] = True

    entry: dict[str, Any] = {"matcher": "*", "hooks": [command_hook]}
    if target == "claude":
        entry["id"] = hook_marker(phase, pid)
        scope_text = "global" if scope_root is None else "project-scoped"
        entry["description"] = f"Capture {phase} events for {scope_text} session learning"
    return entry


def mutate_config(
    payload: dict[str, Any],
    target: str,
    skill_root: Path,
    scope_root: Path | None,
    pid: str,
    uninstall: bool,
) -> dict[str, int]:
    hooks = payload.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("hooks must be a JSON object")

    added = 0
    removed = 0
    for event, phase, timeout in EVENTS:
        had_event = event in hooks
        existing = hooks.get(event, [])
        if not isinstance(existing, list):
            raise ValueError(f"hooks.{event} must be a JSON array")
        kept = []
        for entry in existing:
            if command_has_marker(entry, pid):
                removed += 1
            else:
                kept.append(entry)
        if not uninstall:
            kept.append(target_entry(target, event, phase, timeout, skill_root, scope_root, pid))
            added += 1
        if kept or had_event or not uninstall:
            hooks[event] = kept
    return {"added": added, "removed": removed}


def install_target(
    target: HookTarget,
    skill_root: Path,
    scope_root: Path | None,
    pid: str,
    uninstall: bool,
    dry_run: bool,
) -> dict[str, Any]:
    before = load_config(target.path, target.name)
    after = json.loads(json.dumps(before))
    counts = mutate_config(after, target.name, skill_root, scope_root, pid, uninstall)
    before_text = dump_config(before)
    after_text = dump_config(after)
    changed = before_text != after_text
    backup = write_config(target.path, after, dry_run) if changed else None
    warnings: list[str] = []
    if target.name == "codex" and "easy-release-note/.codex/continuous-learning-v2-observe.sh" in before_text:
        warnings.append("Existing easy-release-note continuous-learning hook detected; left unchanged.")
    return {
        "target": target.name,
        "path": str(target.path),
        "changed": changed,
        "dry_run": dry_run,
        "backup": backup,
        **counts,
        "warnings": warnings,
    }


def command_observe_path(command: str) -> str | None:
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    for part in parts:
        if part.endswith("/observe.sh") or part == "observe.sh":
            return part
    return None


def status_target(target: HookTarget, skill_root: Path, pid: str) -> dict[str, Any]:
    payload = load_config(target.path, target.name)
    expected_observe = str((skill_root / "hooks" / "observe.sh").resolve())
    events: dict[str, Any] = {}
    total_registered = 0
    total_duplicates = 0
    stale_paths: list[dict[str, str]] = []

    for event, _phase, _timeout in EVENTS:
        entries = payload.get("hooks", {}).get(event, [])
        matching = [entry for entry in entries if command_has_marker(entry, pid)] if isinstance(entries, list) else []
        commands: list[str] = []
        for entry in matching:
            entry_command_list = entry_commands(entry)
            if not entry_command_list:
                stale_paths.append({"event": event, "path": "", "reason": "missing command"})
            commands.extend(entry_command_list)
        duplicate_count = max(0, len(matching) - 1)
        total_registered += len(matching)
        total_duplicates += duplicate_count
        for command in commands:
            observe_path = command_observe_path(command)
            if observe_path is None:
                stale_paths.append({"event": event, "path": "", "reason": "missing observe.sh command"})
                continue
            resolved = str(Path(observe_path).expanduser().resolve())
            if resolved != expected_observe:
                stale_paths.append({"event": event, "path": observe_path, "reason": "unexpected observe.sh path"})
            elif not Path(resolved).exists():
                stale_paths.append({"event": event, "path": observe_path, "reason": "observe.sh path does not exist"})
        events[event] = {
            "registered": len(matching),
            "duplicate_count": duplicate_count,
            "commands": commands,
        }

    return {
        "target": target.name,
        "path": str(target.path),
        "exists": target.path.exists(),
        "project_id": pid,
        "registered_events": total_registered,
        "missing_events": [event for event, detail in events.items() if detail["registered"] == 0],
        "duplicate_events": [event for event, detail in events.items() if detail["duplicate_count"] > 0],
        "duplicate_count": total_duplicates,
        "stale_paths": stale_paths,
        "events": events,
    }


def selected_targets(args: argparse.Namespace) -> list[HookTarget]:
    targets: list[HookTarget] = []
    if args.target in {"both", "codex"}:
        targets.append(HookTarget("codex", Path(args.codex_hooks_path).expanduser()))
    if args.target in {"both", "claude"}:
        targets.append(HookTarget("claude", Path(args.claude_hooks_path).expanduser()))
    return targets


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write config changes. Default is dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing.")
    parser.add_argument("--status", action="store_true", help="Inspect hook registration without writing config changes.")
    parser.add_argument("--uninstall", action="store_true", help="Remove this project's session-learning hook entries.")
    parser.add_argument("--target", choices=("both", "codex", "claude"), default="both")
    parser.add_argument("--scope", choices=("project", "global"), default="project")
    parser.add_argument("--global", dest="global_scope", action="store_true", help="Shortcut for --scope global.")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--skill-root", default=str(skill_root_from_script()))
    parser.add_argument("--codex-hooks-path", default=str(default_codex_hooks_path()))
    parser.add_argument("--claude-hooks-path", default=str(default_claude_hooks_path()))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    dry_run = not args.apply or args.dry_run
    scope = "global" if args.global_scope else args.scope
    project_root = detect_project_root(args.project_root)
    skill_root = Path(args.skill_root).expanduser().resolve()
    scope_root = None if scope == "global" else project_root
    pid = "global" if scope == "global" else project_id(project_root)

    if args.status:
        results = [status_target(target, skill_root, pid) for target in selected_targets(args)]
        mode = "status"
    else:
        results = [
            install_target(target, skill_root, scope_root, pid, args.uninstall, dry_run)
            for target in selected_targets(args)
        ]
        mode = "uninstall" if args.uninstall else "install"
    summary = {
        "project_root": None if scope == "global" else str(project_root),
        "project_id": pid,
        "scope": scope,
        "skill_root": str(skill_root),
        "mode": mode,
        "dry_run": True if args.status else dry_run,
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
