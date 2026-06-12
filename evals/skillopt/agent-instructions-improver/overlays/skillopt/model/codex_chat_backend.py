"""Codex CLI optimizer backend for the local Codex-only SkillOpt PoC."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_OUTPUT_ROOT = ".skillopt/outputs/codex-optimizer"

_LAST_TRACE_PATH: str | None = None
_TOKEN_SUMMARY: dict[str, dict[str, int]] = {
    "_total": {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
}
_OPTIMIZER_DEPLOYMENT = ""


@dataclass
class CompatAssistantMessage:
    """Small message object compatible with SkillOpt's chat wrapper callers."""

    content: str
    tool_calls: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        del mode
        return {"role": "assistant", "content": self.content}


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _output_root() -> Path:
    return Path(os.environ.get("CODEX_OPTIMIZER_OUTPUT_ROOT", DEFAULT_OUTPUT_ROOT))


def _new_run_dir(stage: str) -> Path:
    root = _output_root()
    root.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    safe_stage = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in stage)[:60]
    for index in range(1000):
        suffix = f"{index:03d}"
        run_dir = root / f"{timestamp}-{safe_stage}-{suffix}"
        try:
            run_dir.mkdir()
            return run_dir
        except FileExistsError:
            continue
    raise RuntimeError(f"Could not allocate Codex optimizer trace dir under {root}")


def _messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user").strip() or "user"
        content = message.get("content", "")
        if isinstance(content, list):
            content = "\n".join(str(part) for part in content)
        chunks.append(f"## {role}\n{str(content).strip()}")
    return "\n\n".join(chunks).strip()


def _build_exec_prompt(system: str, user: str) -> str:
    sections: list[str] = [
        "You are the SkillOpt optimizer backend for a local Codex-only PoC.",
        "Return only the optimizer response requested by the prompt.",
        "Do not ask follow-up questions.",
        "Do not read API keys, call external model APIs, or use non-Codex providers.",
        "Do not modify files unless the optimizer prompt explicitly requires a file artifact.",
    ]
    if system.strip():
        sections.append(f"## System Prompt\n{system.strip()}")
    if user.strip():
        sections.append(f"## User Prompt\n{user.strip()}")
    return "\n\n".join(sections).strip()


def _record_call(stage: str, prompt: str, completion: str) -> dict[str, int]:
    prompt_tokens = max(1, len(prompt.split()))
    completion_tokens = max(1, len(completion.split())) if completion.strip() else 0
    stage_entry = _TOKEN_SUMMARY.setdefault(
        stage,
        {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    stage_entry["calls"] += 1
    stage_entry["prompt_tokens"] += prompt_tokens
    stage_entry["completion_tokens"] += completion_tokens
    stage_entry["total_tokens"] += prompt_tokens + completion_tokens

    total = _TOKEN_SUMMARY.setdefault(
        "_total",
        {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    total["calls"] += 1
    total["prompt_tokens"] += prompt_tokens
    total["completion_tokens"] += completion_tokens
    total["total_tokens"] += prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _codex_command(prompt: str, output_path: Path, work_dir: Path) -> list[str]:
    codex_bin = os.environ.get("CODEX_EXEC_PATH", "codex").strip() or "codex"
    sandbox = os.environ.get("CODEX_EXEC_SANDBOX", "workspace-write").strip() or "workspace-write"
    approval_policy = os.environ.get("CODEX_EXEC_APPROVAL_POLICY", "never").strip() or "never"
    network_access = _bool_env("CODEX_EXEC_NETWORK_ACCESS", False)
    reasoning_effort = os.environ.get("CODEX_EXEC_REASONING_EFFORT", "medium").strip() or "medium"
    profile = os.environ.get("CODEX_EXEC_PROFILE", "").strip()
    model = _OPTIMIZER_DEPLOYMENT or os.environ.get("CODEX_OPTIMIZER_MODEL", "").strip()

    cmd = [
        codex_bin,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--color",
        "never",
        "--sandbox",
        sandbox,
        "-C",
        str(work_dir),
        "-o",
        str(output_path),
        "-c",
        f"approval_policy={json.dumps(approval_policy)}",
        "-c",
        f"network_access={'true' if network_access else 'false'}",
        "-c",
        f"model_reasoning_effort={json.dumps(reasoning_effort)}",
    ]
    if profile:
        cmd.extend(["-p", profile])
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)
    return cmd


def _run_codex_optimizer(prompt: str, *, stage: str, timeout: int | None) -> tuple[str, dict[str, Any]]:
    global _LAST_TRACE_PATH

    run_dir = _new_run_dir(stage)
    prompt_path = run_dir / "optimizer_prompt.md"
    final_path = run_dir / "last-message.txt"
    stdout_path = run_dir / "codex_stdout.txt"
    stderr_path = run_dir / "codex_stderr.txt"
    command_path = run_dir / "codex_command.txt"
    meta_path = run_dir / "metadata.json"

    prompt_path.write_text(prompt, encoding="utf-8")
    cmd = _codex_command(prompt, final_path, run_dir)
    command_path.write_text(" ".join(shlex.quote(part) for part in cmd) + "\n", encoding="utf-8")

    effective_timeout = timeout or _int_env("CODEX_OPTIMIZER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    started_at = time.time()
    proc = subprocess.run(
        cmd,
        cwd=run_dir,
        text=True,
        capture_output=True,
        timeout=effective_timeout,
        check=False,
    )
    elapsed = time.time() - started_at
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")

    response = final_path.read_text(encoding="utf-8").strip() if final_path.exists() else ""
    usage = _record_call(stage, prompt, response)
    metadata = {
        "backend": "codex_chat",
        "stage": stage,
        "returncode": proc.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "usage": usage,
        "trace_dir": str(run_dir),
        "final_message_path": str(final_path),
    }
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _LAST_TRACE_PATH = str(run_dir)

    if proc.returncode != 0:
        raise RuntimeError(
            "codex_chat optimizer failed with "
            f"exit code {proc.returncode}; trace_dir={run_dir}"
        )
    if not response:
        raise RuntimeError(f"codex_chat optimizer returned an empty response; trace_dir={run_dir}")
    return response, metadata


def chat_optimizer(
    system: str,
    user: str,
    max_completion_tokens: int = 16384,
    retries: int = 5,
    stage: str = "optimizer",
    reasoning_effort: str | None = None,
    timeout: int | None = None,
) -> tuple[str, dict[str, Any]]:
    del max_completion_tokens, retries, reasoning_effort
    prompt = _build_exec_prompt(system, user)
    return _run_codex_optimizer(prompt, stage=stage, timeout=timeout)


def chat_optimizer_messages(
    messages: list[dict[str, Any]],
    max_completion_tokens: int = 16384,
    retries: int = 5,
    stage: str = "optimizer",
    reasoning_effort: str | None = None,
    *,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    return_message: bool = False,
    timeout: int | None = None,
) -> tuple[Any, dict[str, Any]]:
    del max_completion_tokens, retries, reasoning_effort, tools, tool_choice
    prompt = _build_exec_prompt("", _messages_to_prompt(messages))
    response, metadata = _run_codex_optimizer(prompt, stage=stage, timeout=timeout)
    if return_message:
        return CompatAssistantMessage(content=response, metadata=metadata), metadata
    return response, metadata


def chat_with_deployment(
    deployment: str,
    system: str,
    user: str,
    max_completion_tokens: int = 16384,
    retries: int = 5,
    stage: str = "custom",
    reasoning_effort: str | None = None,
    timeout: int | None = None,
) -> tuple[str, dict[str, Any]]:
    set_optimizer_deployment(deployment)
    return chat_optimizer(
        system=system,
        user=user,
        max_completion_tokens=max_completion_tokens,
        retries=retries,
        stage=stage,
        reasoning_effort=reasoning_effort,
        timeout=timeout,
    )


def chat_messages_with_deployment(
    deployment: str,
    messages: list[dict[str, Any]],
    max_completion_tokens: int = 16384,
    retries: int = 5,
    stage: str = "custom",
    reasoning_effort: str | None = None,
    *,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    return_message: bool = False,
    timeout: int | None = None,
) -> tuple[Any, dict[str, Any]]:
    set_optimizer_deployment(deployment)
    return chat_optimizer_messages(
        messages=messages,
        max_completion_tokens=max_completion_tokens,
        retries=retries,
        stage=stage,
        reasoning_effort=reasoning_effort,
        tools=tools,
        tool_choice=tool_choice,
        return_message=return_message,
        timeout=timeout,
    )


def get_token_summary() -> dict[str, dict[str, int]]:
    return json.loads(json.dumps(_TOKEN_SUMMARY))


def reset_token_tracker() -> None:
    _TOKEN_SUMMARY.clear()
    _TOKEN_SUMMARY["_total"] = {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def set_optimizer_deployment(deployment: str) -> None:
    global _OPTIMIZER_DEPLOYMENT
    _OPTIMIZER_DEPLOYMENT = str(deployment or "").strip()


def get_last_trace_path() -> str | None:
    return _LAST_TRACE_PATH
