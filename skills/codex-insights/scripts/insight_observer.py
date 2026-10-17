#!/usr/bin/env python3
"""Project-local Codex Insights observer.

This script is intentionally conservative: it records observations under
`.omx/learning` and never edits canonical project files.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SKIP_PATH_PARTS = ("observer-sessions", ".claude-mem", ".omx/learning")
OUTCOME_SCAN_LIMIT = 4000
PHASE_CATEGORIES = frozenset({"prompt", "pre", "post", "stop", "pre-compact", "post-compact"})
ROOT_SOURCE_CATEGORIES = frozenset({"git", "env", "cwd-fallback"})
EXPLICIT_GIT_ENV = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_LITERAL_PATHSPECS",
    "GIT_GLOB_PATHSPECS",
    "GIT_NOGLOB_PATHSPECS",
    "GIT_ICASE_PATHSPECS",
)


class UnsafeStoragePath(RuntimeError):
    """Raised when observer storage could escape or follow a symlink."""


def insight_env(name: str) -> str | None:
    legacy_name = name.replace("CODEX_INSIGHTS_", "SESSION_LEARNING_", 1)
    return os.environ.get(name, os.environ.get(legacy_name))


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def slug_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")


def stable_identifier(value: Any, kind: str, project: str) -> str:
    raw = str(value or "")
    if not raw:
        return f"{kind}-unknown" if kind == "session" else ""
    digest = hashlib.sha256(f"{project}\0{kind}\0{raw}".encode()).hexdigest()[:16]
    return f"{kind}-{digest}"


def cwd_category(cwd_text: Any, root: Path) -> str:
    if not cwd_text:
        return "unknown"
    try:
        relative = Path(str(cwd_text)).expanduser().resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return "outside-project"
    return "project-root" if relative == Path() else "inside-project"


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


def trusted_git_path(path: Path) -> bool:
    trusted_owners = {0, os.geteuid()}
    child = path.stat()
    if child.st_uid not in trusted_owners or child.st_mode & 0o022:
        return False
    for directory in path.parents:
        parent = directory.stat()
        if parent.st_uid not in trusted_owners:
            return False
        if parent.st_mode & 0o022 and (
            not parent.st_mode & stat.S_ISVTX or child.st_uid not in trusted_owners
        ):
            return False
        child = parent
    return True


def resolve_git_executable(cwd: Path) -> str:
    try:
        boundary = cwd.resolve(strict=True)
        for candidate in (boundary, *boundary.parents):
            try:
                (candidate / ".git").lstat()
            except FileNotFoundError:
                continue
            boundary = candidate
            break
    except OSError as exc:
        raise FileNotFoundError("could not validate git executable") from exc

    path_value = os.environ.get("PATH", os.defpath)
    seen: set[Path] = set()
    for entry in path_value.split(os.pathsep):
        directory = Path(entry)
        if not entry or not directory.is_absolute():
            continue
        executable = shutil.which("git", path=str(directory))
        if not executable:
            continue
        try:
            resolved = Path(executable).resolve(strict=True)
            if resolved in seen:
                continue
            seen.add(resolved)
            if not resolved.is_file() or not os.access(resolved, os.X_OK):
                continue
            if any(component.samefile(boundary) for component in (resolved, *resolved.parents)):
                continue
            if not trusted_git_path(resolved):
                continue
        except OSError:
            continue
        return str(resolved)
    raise FileNotFoundError("trusted git executable not found")


def git_subprocess_env(git: str) -> dict[str, str]:
    path_entries = [str(Path(git).parent)]
    path_entries.extend(
        entry for entry in os.defpath.split(os.pathsep) if entry and Path(entry).is_absolute()
    )
    return {
        "PATH": os.pathsep.join(dict.fromkeys(path_entries)),
        "TMPDIR": "/tmp",
        "LC_ALL": "C",
        "LANG": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }


def run_git_checked(args: list[str], cwd: Path) -> tuple[str, str | None]:
    try:
        git = resolve_git_executable(cwd)
        result = subprocess.run(
            [git, "-c", f"core.excludesFile={os.devnull}", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
            env=git_subprocess_env(git),
        )
    except FileNotFoundError:
        return "", "git_not_found"
    except subprocess.TimeoutExpired:
        return "", "git_timeout"
    if result.returncode != 0:
        stderr = result.stderr.strip().splitlines()
        detail = stderr[0] if stderr else f"exit_{result.returncode}"
        return "", f"git_failed:{detail}"
    return result.stdout.strip(), None


def run_git(args: list[str], cwd: Path) -> str:
    output, _ = run_git_checked(args, cwd)
    return output


def run_git_policy_command(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    if any(name in os.environ for name in EXPLICIT_GIT_ENV):
        raise UnsafeStoragePath("explicit Git environment is not allowed for storage policy")
    try:
        git = resolve_git_executable(cwd)
        return subprocess.run(
            [git, "-c", f"core.excludesFile={os.devnull}", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
            env=git_subprocess_env(git),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise UnsafeStoragePath("could not verify Git storage policy") from exc


def root_from_cwd(cwd_text: str | None) -> tuple[Path, str, str | None]:
    cwd = Path(cwd_text or os.getcwd()).expanduser()
    if not cwd.exists():
        cwd = Path(os.getcwd())
    cwd = cwd.resolve()

    git_root, warning = run_git_checked(["rev-parse", "--show-toplevel"], cwd)
    if git_root:
        return Path(git_root).resolve(), "git", None
    return cwd, "cwd-fallback", warning


def detect_project_root(cwd_text: str | None) -> tuple[Path, str, str | None]:
    env_root = insight_env("CODEX_INSIGHTS_PROJECT_DIR")
    event_root, event_source, event_warning = root_from_cwd(cwd_text)
    if env_root:
        candidate = Path(env_root).expanduser()
        if not candidate.is_dir():
            return event_root, event_source, "env_project_dir_not_directory"
        resolved = candidate.resolve()
        if not cwd_text:
            return resolved, "env", None
        scope = scope_root()
        allowed = path_contains(event_root, resolved) or path_contains(resolved, event_root)
        if scope is not None:
            allowed = allowed and path_contains(resolved, scope)
        if not allowed:
            return event_root, event_source, "env_project_dir_rejected:outside-event-root"
        return resolved, "env", None
    return event_root, event_source, event_warning


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
    scope = insight_env("CODEX_INSIGHTS_SCOPE_ROOT")
    if not scope:
        return None
    path = Path(scope).expanduser()
    if not path.is_dir():
        return None
    return path.resolve()


def should_skip(
    payload: dict[str, Any], root: Path, cwd_text: str | None, event_root: Path
) -> bool:
    if insight_env("CODEX_INSIGHTS_DISABLED") == "1":
        return True
    if os.environ.get("ECC_SKIP_OBSERVE") == "1":
        return True
    if payload.get("agent_id"):
        return True
    scope = scope_root()
    if insight_env("CODEX_INSIGHTS_SCOPE_ROOT") and scope is None:
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


def validate_storage_path(path: Path, root: Path) -> None:
    storage_parts(path, root)


def storage_parts(path: Path, root: Path) -> tuple[Path, tuple[str, ...]]:
    absolute_root = Path(os.path.abspath(root))
    resolved_root = absolute_root.resolve(strict=True)
    absolute_path = Path(os.path.abspath(path))
    relative: Path | None = None
    for root_form in (absolute_root, resolved_root):
        try:
            relative = absolute_path.relative_to(root_form)
            break
        except ValueError:
            pass
    if relative is None:
        raise UnsafeStoragePath(f"path escapes project root: {path}")
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise UnsafeStoragePath("storage path must be below project root")
    return resolved_root, relative.parts


def directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def open_directory_at(parent_descriptor: int, name: str) -> int:
    try:
        descriptor = os.open(name, directory_flags(), dir_fd=parent_descriptor)
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise UnsafeStoragePath(f"symlink is not allowed: {name}") from exc
        raise
    try:
        opened = os.fstat(descriptor)
        current = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        if not stat.S_ISDIR(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            current.st_dev,
            current.st_ino,
        ):
            raise UnsafeStoragePath(f"directory changed while opening: {name}")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def open_storage_directory(root: Path, parts: tuple[str, ...]) -> int:
    descriptor = os.open(root, directory_flags())
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise UnsafeStoragePath(f"project root is not a directory: {root}")
        for part in parts:
            next_descriptor = open_directory_at(descriptor, part)
            os.close(descriptor)
            descriptor = next_descriptor
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def require_git_ignored_untracked(path: Path, root: Path) -> None:
    root, parts = storage_parts(path, root)
    path = root.joinpath(*parts)
    for index in range(1, len(parts)):
        marker = root.joinpath(*parts[:index], ".git")
        try:
            marker.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UnsafeStoragePath(f"could not inspect nested Git boundary: {marker}") from exc
        raise UnsafeStoragePath(f"nested Git boundary is not allowed: {marker}")

    probe = run_git_policy_command(["rev-parse", "--show-toplevel"], root)
    if probe.returncode != 0:
        error_lines = probe.stderr.strip().casefold().splitlines()
        boundary_line = "stopping at filesystem boundary (git_discovery_across_filesystem not set)."
        if (
            probe.returncode == 128
            and len(error_lines) in {1, 2}
            and error_lines[0].startswith(
                ("fatal: not a git repository ", "fatal: not a git repository:")
            )
            and (len(error_lines) == 1 or error_lines[1] == boundary_line)
        ):
            return
        raise UnsafeStoragePath("could not verify Git storage policy")
    git_root_text = probe.stdout.strip()
    if not git_root_text:
        raise UnsafeStoragePath("Git worktree probe returned no root")

    try:
        git_root = Path(git_root_text).resolve(strict=True)
        relative = path.relative_to(git_root).as_posix()
    except (OSError, ValueError) as exc:
        raise UnsafeStoragePath(f"storage path is outside Git worktree: {path}") from exc

    relative_parts = Path(relative).parts
    prefixes = [Path(*relative_parts[:index]).as_posix() for index in range(1, len(relative_parts))]
    if prefixes:
        prefix_pathspecs = [f":(icase,literal){prefix}" for prefix in prefixes]
        gitlinks = run_git_policy_command(
            ["ls-files", "--stage", "-z", "--", *prefix_pathspecs], git_root
        )
        if gitlinks.returncode != 0:
            raise UnsafeStoragePath("could not verify Git storage prefixes")
        folded_prefixes = {prefix.casefold() for prefix in prefixes}
        for entry in gitlinks.stdout.split("\0"):
            if not entry:
                continue
            try:
                metadata, index_path = entry.split("\t", 1)
            except ValueError as exc:
                raise UnsafeStoragePath("malformed Git storage prefix result") from exc
            fields = metadata.split()
            if len(fields) != 3:
                raise UnsafeStoragePath("malformed Git storage prefix metadata")
            if fields[0] == "160000" and index_path.casefold() in folded_prefixes:
                raise UnsafeStoragePath(f"Gitlink storage prefix is not allowed: {path}")

    tracked_pathspec = f":(icase,literal){relative}"
    tracked = run_git_policy_command(
        ["ls-files", "--error-unmatch", "--", tracked_pathspec], git_root
    )
    if tracked.returncode == 0:
        raise UnsafeStoragePath(f"Git-tracked storage path is not allowed: {path}")
    if tracked.returncode != 1:
        raise UnsafeStoragePath(f"could not verify untracked storage path: {path}")

    ignored = run_git_policy_command(
        ["check-ignore", "--quiet", "--no-index", "--", relative],
        git_root,
    )
    if ignored.returncode != 0:
        raise UnsafeStoragePath(f"Git storage path must be ignored: {path}")


def secure_directory(path: Path, root: Path, *, preserve_existing_mode: bool = False) -> None:
    absolute_root, parts = storage_parts(path, root)
    parent_descriptor = open_storage_directory(absolute_root, parts[:-1])
    try:
        created = False
        try:
            os.mkdir(parts[-1], mode=0o700, dir_fd=parent_descriptor)
            created = True
        except FileExistsError:
            pass
        descriptor = open_directory_at(parent_descriptor, parts[-1])
        try:
            if created or not preserve_existing_mode:
                os.fchmod(descriptor, 0o700)
        finally:
            os.close(descriptor)
    finally:
        os.close(parent_descriptor)


def secure_file_descriptor(path: Path, root: Path, flags: int) -> int:
    absolute_root, parts = storage_parts(path, root)
    writable = (flags & os.O_ACCMODE) != os.O_RDONLY
    if writable:
        require_git_ignored_untracked(absolute_root.joinpath(*parts), absolute_root)
    parent_descriptor = open_storage_directory(absolute_root, parts[:-1])
    try:
        try:
            descriptor = os.open(
                parts[-1],
                flags | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=parent_descriptor,
            )
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise UnsafeStoragePath(f"symlink is not allowed: {path}") from exc
            raise
        try:
            opened = os.fstat(descriptor)
            current = os.stat(parts[-1], dir_fd=parent_descriptor, follow_symlinks=False)
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
                current.st_dev,
                current.st_ino,
            ):
                raise UnsafeStoragePath(f"file changed while opening: {path}")
            if writable:
                os.fchmod(descriptor, 0o600)
        except BaseException:
            os.close(descriptor)
            raise
    finally:
        os.close(parent_descriptor)
    return descriptor


def learning_dirs(root: Path) -> dict[str, Path]:
    root = root.resolve(strict=True)
    omx = root / ".omx"
    base = root / ".omx" / "learning"
    paths = {
        "base": base,
        "observations": base / "observations.jsonl",
        "candidates": base / "candidates",
        "promoted": base / "promoted",
        "archive": base / "archive",
    }
    secure_directory(omx, root, preserve_existing_mode=True)
    secure_directory(base, root)
    for key, path in paths.items():
        if key != "observations":
            secure_directory(path, root)
    validate_storage_path(paths["observations"], root)
    return paths


def build_observation(
    phase: str,
    payload: dict[str, Any],
    raw_error: str | None,
    root: Path,
    root_source: str,
    root_warning: str | None,
) -> dict[str, Any]:
    cwd_text = first_present(payload, ("cwd", "working_directory", "workdir"))
    tool_input = first_present(
        payload, ("tool_input", "input", "arguments", "params", "prompt", "user_prompt")
    )
    tool_output = first_present(
        payload, ("tool_response", "tool_output", "output", "result", "error")
    )
    safe_phase = phase if phase in PHASE_CATEGORIES else "other"
    current_project_id = project_id(root)
    source = "configured" if insight_env("CODEX_INSIGHTS_SOURCE") else "default"
    tool = stable_identifier(
        first_present(payload, ("tool_name", "tool", "name")),
        "tool-name",
        current_project_id,
    )
    observation: dict[str, Any] = {
        "timestamp": utc_now(),
        "source": source,
        "phase": safe_phase,
        "session_id": stable_identifier(
            first_present(payload, ("session_id", "conversation_id", "thread_id")),
            "session",
            current_project_id,
        ),
        "tool_use_id": stable_identifier(
            first_present(payload, ("tool_use_id", "call_id")), "tool", current_project_id
        ),
        "cwd": cwd_category(cwd_text, root),
        "project_root": "[project-root]",
        "root_source": root_source if root_source in ROOT_SOURCE_CATEGORIES else "other",
        "project_id": current_project_id,
        "tool": tool or "tool-name-unknown",
        "content_policy": "metadata-only",
        "outcome_signal": infer_outcome(
            safe_phase, tool_input, tool_output, parse_error=raw_error is not None
        ),
    }
    if root_warning:
        observation["root_warning"] = root_warning_category(root_warning)
    return observation


def root_warning_category(warning: str) -> str:
    if warning == "env_project_dir_not_directory":
        return "env-project-dir-invalid"
    if warning.startswith("env_project_dir_rejected:"):
        return "env-project-dir-rejected"
    if warning == "git_not_found":
        return "git-not-found"
    if warning == "git_timeout":
        return "git-timeout"
    if warning.startswith("git_failed:"):
        return "git-failed"
    return "other"


def outcome_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError, RecursionError):
        return ""
    return text[:OUTCOME_SCAN_LIMIT].casefold()


def infer_outcome(
    phase: str, tool_input: Any, tool_output: Any, *, parse_error: bool = False
) -> str:
    if parse_error:
        return "parse_error"
    if phase in {"stop", "pre-compact", "post-compact"}:
        return phase
    text = f"{outcome_text(tool_input)}\n{outcome_text(tool_output)}"
    if any(
        marker in text
        for marker in ("traceback", "error", "failed", "exception", "permission denied")
    ):
        return "error-signal"
    if any(marker in text for marker in ("pass", "success", "approved", "complete", "exit code 0")):
        return "success-signal"
    if any(
        marker in text
        for marker in ("actually", "instead", "always", "next time", "don't", "do not")
    ):
        return "correction-or-preference-signal"
    return "observed"


def append_jsonl(path: Path, payload: dict[str, Any], root: Path) -> None:
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    descriptor = secure_file_descriptor(path, root, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def recent_session_observations(
    path: Path, session_id: str, root: Path, limit: int = 200
) -> list[dict[str, Any]]:
    if path.is_symlink():
        raise UnsafeStoragePath(f"symlink is not allowed: {path}")
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    descriptor = secure_file_descriptor(path, root, os.O_RDONLY)
    with os.fdopen(descriptor, encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("session_id") == session_id:
                rows.append(row)
    return rows[-limit:]


def write_stop_candidate(
    paths: dict[str, Path], observation: dict[str, Any], candidate_path: Path | None = None
) -> Path:
    root = paths["base"].parents[1].resolve(strict=True)
    session_id = observation.get("session_id", "unknown")
    if candidate_path is None:
        safe_session = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(session_id))[:48] or "unknown"
        candidate_path = unique_candidate_path(paths["candidates"], safe_session)
    recent = recent_session_observations(paths["observations"], str(session_id), root)
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
        "# Codex Insights Candidate",
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
        "- `subagent`: bounded specialist role, recurring investigation, review pass, or research task.",
        "- `archive`: weak, duplicate, stale, or session-specific.",
        "",
    ]
    descriptor = secure_file_descriptor(
        candidate_path,
        root,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write("\n".join(body))
        handle.flush()
        os.fsync(handle.fileno())
    return candidate_path


def unique_candidate_path(directory: Path, safe_session: str) -> Path:
    for index in range(100):
        suffix = f"-{index}" if index else ""
        path = directory / f"{slug_timestamp()}-{safe_session}{suffix}.md"
        if path.is_symlink():
            raise UnsafeStoragePath(f"symlink is not allowed: {path}")
        if not path.exists():
            return path
    raise RuntimeError("could not allocate unique stop candidate path")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="post")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    raw = sys.stdin.read()
    payload, raw_error = load_payload(raw)
    cwd_text = first_present(payload, ("cwd", "working_directory", "workdir"))
    event_root, _, _ = root_from_cwd(str(cwd_text) if cwd_text else None)
    root, root_source, root_warning = detect_project_root(str(cwd_text) if cwd_text else None)
    scope = scope_root()
    if scope is not None:
        root = scope
    if should_skip(payload, root, str(cwd_text) if cwd_text else None, event_root):
        return 0

    observation = build_observation(args.phase, payload, raw_error, root, root_source, root_warning)
    if args.dry_run:
        print(json.dumps(observation, ensure_ascii=False, sort_keys=True))
        return 0

    base = root.resolve(strict=True) / ".omx" / "learning"
    observations_path = base / "observations.jsonl"
    require_git_ignored_untracked(observations_path, root)
    candidate_path = None
    if args.phase == "stop":
        session_id = observation.get("session_id", "unknown")
        safe_session = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(session_id))[:48] or "unknown"
        candidate_path = unique_candidate_path(base / "candidates", safe_session)
        require_git_ignored_untracked(candidate_path, root)

    paths = learning_dirs(root)
    append_jsonl(paths["observations"], observation, root)
    if args.phase == "stop":
        written_candidate = write_stop_candidate(paths, observation, candidate_path)
        print(f"[codex-insights] wrote {written_candidate}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
