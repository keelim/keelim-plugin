"""Rollout harness for the agent-instructions-improver SkillOpt PoC."""

from __future__ import annotations

import json
import os
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

from skillopt.envs.agent_instructions_improver.evaluator import evaluate
from skillopt.model import chat_target, is_target_exec_backend

try:
    from skillopt.model import azure_openai as _llm
    from skillopt.model.codex_harness import prepare_workspace, render_skill_md, run_target_exec
except Exception:  # pragma: no cover - imported only inside prepared SkillOpt checkout
    _llm = None  # type: ignore[assignment]
    prepare_workspace = None  # type: ignore[assignment]
    render_skill_md = None  # type: ignore[assignment]
    run_target_exec = None  # type: ignore[assignment]


def _item_text(item: dict[str, Any], key: str, default: str = "") -> str:
    return str(item.get(key) or default)


def build_user_prompt(item: dict[str, Any]) -> str:
    sections = [
        "# Agent Instruction Improvement Task",
        "",
        "Produce the quality report and targeted recommendations requested by the task.",
        "Ground the response only in the redacted repository context below.",
        "",
        "## Task",
        _item_text(item, "task", "Audit the agent instruction guidance and recommend improvements."),
        "",
        "## Repository Context",
        _item_text(item, "repository_context", "No repository context supplied."),
        "",
        "## Current Instruction Excerpt",
        _item_text(item, "current_instruction_excerpt", "No instruction excerpt supplied."),
        "",
        "## Response Contract",
        "- Report source-of-truth guidance when relevant.",
        "- Name concrete command, architecture, currency, or boundary gaps when present.",
        "- Do not claim a provider, API key, or rewrite is required unless the task states it.",
        "- Do not modify files; return only the report/recommendation text.",
    ]
    return "\n".join(sections)


def build_system_prompt(skill_content: str) -> str:
    skill = skill_content.strip()
    if skill:
        return (
            "Use the following skill guidance while answering this agent instruction task.\n\n"
            f"## Skill\n{skill}"
        )
    return "Answer the agent instruction improvement task using repository evidence only."


def _build_codex_skill(skill_content: str) -> str:
    if render_skill_md is None:
        raise RuntimeError("SkillOpt codex_harness is unavailable")
    return render_skill_md(
        skill_content,
        description="Dynamic SkillOpt skill for improving agent instruction files.",
        preamble=(
            "Use this skill when producing an agent instruction quality report. "
            "Read task.md and stay within the redacted repository context."
        ),
    )


def _run_codex_target(
    *,
    pred_dir: Path,
    skill_content: str,
    item: dict[str, Any],
    model: str,
    timeout: int,
) -> tuple[str, str, str]:
    if prepare_workspace is None or run_target_exec is None:
        raise RuntimeError("SkillOpt codex_harness is unavailable")
    task_text = build_user_prompt(item)
    skill_md = _build_codex_skill(skill_content)
    work_dir = pred_dir / "codex_exec"
    prepare_workspace(work_dir=str(work_dir), skill_md=skill_md, task_text=task_text)
    prompt = (
        "Read `.agents/skills/skillopt-target/SKILL.md` and `task.md` directly. "
        "Return only the agent instruction quality report/recommendation text. "
        "Do not modify files."
    )
    final_message, raw = run_target_exec(
        work_dir=str(work_dir),
        prompt=prompt,
        model=model,
        timeout=timeout,
    )
    return final_message or raw, skill_md, task_text


def process_one(
    item: dict[str, Any],
    out_root: str,
    skill_content: str,
    max_turns: int = 1,
    diagnostic_mode: bool = False,
    diagnostic_instruction: str = "",
    diagnostic_trace_context: str = "",
    exec_timeout: int = 180,
    max_completion_tokens: int = 12000,
) -> dict[str, Any]:
    del max_turns, diagnostic_mode, diagnostic_instruction, diagnostic_trace_context

    item_id = str(item.get("id") or f"item-{abs(hash(json.dumps(item, sort_keys=True))) % 100000}")
    pred_dir = Path(out_root) / "predictions" / item_id
    pred_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "id": item_id,
        "task_description": _item_text(item, "task"),
        "task_type": item.get("task_type") or "agent_instructions_improver",
        "hard": 0,
        "soft": 0.0,
        "response": "",
        "fail_reason": "",
        "agent_ok": False,
        "n_turns": 0,
    }

    try:
        if is_target_exec_backend():
            model = getattr(_llm, "TARGET_DEPLOYMENT", "") if _llm is not None else ""
            response, system, user = _run_codex_target(
                pred_dir=pred_dir,
                skill_content=skill_content,
                item=item,
                model=model,
                timeout=exec_timeout,
            )
        else:
            system = build_system_prompt(skill_content)
            user = build_user_prompt(item)
            response, _ = chat_target(
                system=system,
                user=user,
                max_completion_tokens=max_completion_tokens,
                retries=5,
                stage="rollout",
                timeout=exec_timeout,
            )
        eval_result = evaluate(response, item.get("expected") or {})
        result.update(eval_result)
        result["response"] = response
        result["agent_ok"] = True
        result["n_turns"] = 1
        if result["hard"] != 1:
            result["fail_reason"] = (
                f"missing={eval_result['missing']} violations={eval_result['violations']}"
            )
        (pred_dir / "target_system_prompt.txt").write_text(system, encoding="utf-8")
        (pred_dir / "target_user_prompt.txt").write_text(user, encoding="utf-8")
        (pred_dir / "conversation.json").write_text(
            json.dumps(
                [
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": response},
                    {"role": "system", "content": json.dumps(eval_result, sort_keys=True)},
                ],
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        result["fail_reason"] = f"error: {type(exc).__name__}: {exc}"
        (pred_dir / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    return result


def run_batch(
    items: list[dict[str, Any]],
    out_root: str,
    skill_content: str,
    max_turns: int = 1,
    exec_timeout: int = 180,
    workers: int = 1,
    max_completion_tokens: int = 12000,
    diagnostic_mode: bool = False,
    diagnostic_instruction: str = "",
    diagnostic_trace_context_by_id: dict[str, str] | None = None,
    task_timeout: int = 600,
) -> list[dict[str, Any]]:
    del diagnostic_trace_context_by_id

    os.makedirs(out_root, exist_ok=True)
    results_path = Path(out_root) / "results.jsonl"
    done_ids: set[str] = set()
    results: list[dict[str, Any]] = []
    if results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            done_ids.add(str(row.get("id")))
            results.append(row)

    pending = [item for item in items if str(item.get("id")) not in done_ids]
    if not pending:
        return results

    task_timeout = max(int(task_timeout), int(exec_timeout) + 60)
    started_at: dict[str, float] = {}

    def _timeout_result(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(item.get("id")),
            "task_description": _item_text(item, "task"),
            "task_type": item.get("task_type") or "agent_instructions_improver",
            "hard": 0,
            "soft": 0.0,
            "response": "",
            "fail_reason": f"task-timeout-{task_timeout}s",
            "agent_ok": False,
            "n_turns": 0,
        }

    def _run(item: dict[str, Any]) -> dict[str, Any]:
        started_at[str(item.get("id"))] = time.time()
        return process_one(
            item,
            out_root,
            skill_content,
            max_turns=max_turns,
            diagnostic_mode=diagnostic_mode,
            diagnostic_instruction=diagnostic_instruction,
            exec_timeout=exec_timeout,
            max_completion_tokens=max_completion_tokens,
        )

    with results_path.open("a", encoding="utf-8") as handle:
        executor = ThreadPoolExecutor(max_workers=max(1, int(workers)))
        try:
            futures = {executor.submit(_run, item): item for item in pending}
            pending_futures = set(futures)
            while pending_futures:
                done, _ = wait(pending_futures, timeout=5, return_when=FIRST_COMPLETED)
                now = time.time()
                timed_out = [
                    future
                    for future in pending_futures - done
                    if str(futures[future].get("id")) in started_at
                    and now - started_at[str(futures[future].get("id"))] >= task_timeout
                ]
                for future in done:
                    pending_futures.remove(future)
                    try:
                        row = future.result()
                    except Exception as exc:  # noqa: BLE001
                        row = _timeout_result(futures[future])
                        row["fail_reason"] = f"unexpected: {type(exc).__name__}: {exc}"
                    results.append(row)
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    handle.flush()
                for future in timed_out:
                    pending_futures.remove(future)
                    future.cancel()
                    row = _timeout_result(futures[future])
                    results.append(row)
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    handle.flush()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    return results

