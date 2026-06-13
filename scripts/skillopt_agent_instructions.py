#!/usr/bin/env python3
"""Codex-only SkillOpt pilot runner for agent-instructions-improver."""

from __future__ import annotations

import argparse
import ast
import difflib
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
POC_DIR = REPO_ROOT / "evals" / "skillopt" / "agent-instructions-improver"
OVERLAY_DIR = POC_DIR / "overlays"
CONFIG_SRC = POC_DIR / "configs" / "agent_instructions_improver" / "codex_only.yaml"
FIXTURE_PATH = POC_DIR / "fixtures" / "score-fixture.json.sample"
SKILL_PATH = REPO_ROOT / "skills" / "agent-instructions-improver" / "SKILL.md"
SKILLOPT_ROOT = REPO_ROOT / ".skillopt"
SKILLOPT_CHECKOUT = SKILLOPT_ROOT / "SkillOpt"
UV_CACHE = SKILLOPT_ROOT / "uv-cache"
DATA_DIR = SKILLOPT_ROOT / "data" / "agent-instructions-improver-v1"
OUTPUT_ROOT = SKILLOPT_ROOT / "outputs" / "agent-instructions-improver"
CODEX_OPTIMIZER_OUTPUT_ROOT = SKILLOPT_ROOT / "outputs" / "codex-optimizer"
TRUST_CODEX_EXEC_ENV = "KEELIM_PLUGIN_TRUST_CODEX_EXEC"


BANNED_ENV_KEYS = {
    "ANTHROPIC_API_KEY",
    "CLAUDE_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_AUTH_MODE",
    "QWEN_API_KEY",
    "QWEN_CHAT_BASE_URL",
    "QWEN_CHAT_MODEL",
    "MINIMAX_API_KEY",
    "MINIMAX_BASE_URL",
    "MINIMAX_MODEL",
    "VLLM_API_KEY",
}
BANNED_ENV_PREFIXES = ("ANTHROPIC_", "AZURE_OPENAI_", "QWEN_", "MINIMAX_")
SAFE_ENV_KEYS = {
    "CODEX_HOME",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "PWD",
    "SHELL",
    "TMPDIR",
    "USER",
}
SAFE_ENV_PREFIXES = ("PYTHON", "UV_", "VIRTUAL_ENV")


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def run(
    cmd: list[str],
    *,
    cwd: Path = REPO_ROOT,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=capture,
        check=False,
    )
    if check and proc.returncode != 0:
        if capture:
            if proc.stdout:
                eprint(proc.stdout.rstrip())
            if proc.stderr:
                eprint(proc.stderr.rstrip())
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc


def uv_python_cmd(*python_args: str) -> list[str]:
    return [
        "uv",
        "--cache-dir",
        str(UV_CACHE),
        "run",
        "--python",
        "3.12",
        "python",
        *python_args,
    ]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def score_response(response: str, expected: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_text(response)
    must_find = [str(item) for item in expected.get("must_find", [])]
    forbidden = [
        str(item) for group in ("must_not_claim", "must_not_do") for item in expected.get(group, [])
    ]
    found = [item for item in must_find if normalize_text(item) in normalized]
    missing = [item for item in must_find if item not in found]
    violations = [item for item in forbidden if normalize_text(item) in normalized]
    required_fraction = len(found) / len(must_find) if must_find else 1.0
    no_forbidden = 1.0 if not violations else 0.0
    return {
        "hard": int(required_fraction == 1.0 and no_forbidden == 1.0),
        "soft": round((0.8 * required_fraction) + (0.2 * no_forbidden), 4),
        "found": found,
        "missing": missing,
        "violations": violations,
    }


def default_examples() -> list[dict[str, Any]]:
    return [
        {
            "id": "seed-source-of-truth-001",
            "task_type": "agent_instructions_improver",
            "task": "Audit shared and platform-specific agent instruction files.",
            "repository_context": (
                "Repository has AGENTS.md plus platform-specific entry points. "
                "The user wants reusable instructions for multiple agents."
            ),
            "current_instruction_excerpt": (
                "Build commands are incomplete and platform-specific files repeat shared guidance."
            ),
            "expected": {
                "must_find": ["AGENTS.md", "platform-specific", "commands"],
                "must_not_claim": ["Claude is required", "OpenAI API key is required"],
                "must_not_do": ["rewrite unrelated files"],
            },
        },
        {
            "id": "seed-child-boundary-002",
            "task_type": "agent_instructions_improver",
            "task": "Review agent guidance for a root coordination repo with autonomous children.",
            "repository_context": (
                "The root coordinates child repositories. Child source edits require entering "
                "the child repo and following its own AGENTS.md."
            ),
            "current_instruction_excerpt": (
                "Instructions mention child repos but do not warn against root-level rewrites."
            ),
            "expected": {
                "must_find": ["child repo", "boundary", "AGENTS.md"],
                "must_not_claim": ["convert to a monorepo", "reset child changes"],
                "must_not_do": ["discard user changes"],
            },
        },
        {
            "id": "seed-commands-003",
            "task_type": "agent_instructions_improver",
            "task": "Find gaps in an instruction file for future testing sessions.",
            "repository_context": "The README lists smoke tests but AGENTS.md omits exact commands.",
            "current_instruction_excerpt": "Run tests before finishing.",
            "expected": {
                "must_find": ["copy-paste", "test", "command"],
                "must_not_claim": ["all tests pass without running them"],
                "must_not_do": ["invent commands"],
            },
        },
        {
            "id": "seed-private-overrides-004",
            "task_type": "agent_instructions_improver",
            "task": "Recommend how to handle local/private agent overrides.",
            "repository_context": "There is a shared AGENTS.md and ignored local override files.",
            "current_instruction_excerpt": "Local preferences are mixed into the shared guide.",
            "expected": {
                "must_find": ["local", "private", "shared"],
                "must_not_claim": ["commit private overrides", "delete local overrides"],
                "must_not_do": ["expose secrets"],
            },
        },
        {
            "id": "seed-currency-005",
            "task_type": "agent_instructions_improver",
            "task": "Assess whether an agent instruction file is current.",
            "repository_context": "Scripts changed names recently and stale commands remain in docs.",
            "current_instruction_excerpt": "Use npm test, but the repo now uses bun run test.",
            "expected": {
                "must_find": ["stale", "current", "command"],
                "must_not_claim": ["npm is definitely correct"],
                "must_not_do": ["normalize unrelated docs"],
            },
        },
        {
            "id": "seed-concise-006",
            "task_type": "agent_instructions_improver",
            "task": "Improve a verbose instruction file without losing important project facts.",
            "repository_context": "The guide repeats generic best practices and hides a real deployment gotcha.",
            "current_instruction_excerpt": "Long generic sections repeat normal coding advice.",
            "expected": {
                "must_find": ["concise", "project-specific", "gotcha"],
                "must_not_claim": ["remove all detail"],
                "must_not_do": ["drop important warnings"],
            },
        },
        {
            "id": "seed-report-first-007",
            "task_type": "agent_instructions_improver",
            "task": "Respond to a request to update AGENTS.md immediately.",
            "repository_context": "The skill contract requires a quality report before changes.",
            "current_instruction_excerpt": "No score or issue list is present yet.",
            "expected": {
                "must_find": ["quality report", "before", "update"],
                "must_not_claim": ["approval is unnecessary"],
                "must_not_do": ["apply changes before reporting"],
            },
        },
        {
            "id": "seed-no-provider-drift-008",
            "task_type": "agent_instructions_improver",
            "task": "Audit instructions without changing model/provider policy.",
            "repository_context": "The repo supports multiple agents, but this task is not about provider setup.",
            "current_instruction_excerpt": "No API credentials are required for the instruction audit.",
            "expected": {
                "must_find": ["multiple agents", "instruction audit", "evidence"],
                "must_not_claim": ["API key is required", "Claude is required", "Qwen is required"],
                "must_not_do": ["add provider secrets"],
            },
        },
    ]


def observations_paths() -> list[Path]:
    candidates = [REPO_ROOT / ".omx" / "learning" / "observations.jsonl"]
    candidates.extend(
        Path(path)
        for path in glob.glob(str(REPO_ROOT / ".omx" / "learning" / "observations*.jsonl"))
    )
    return sorted({path for path in candidates if path.exists()})


def keywords_from_text(text: str) -> list[str]:
    keywords = []
    for keyword in [
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        "Copilot",
        "Cursor",
        "skill",
        "instruction",
        "test",
        "command",
        "boundary",
    ]:
        if keyword.lower() in text.lower():
            keywords.append(keyword)
    return keywords


def curated_from_observations(limit: int) -> tuple[list[dict[str, Any]], int, list[str]]:
    examples: list[dict[str, Any]] = []
    seen = 0
    parse_warnings: list[str] = []
    for path in observations_paths():
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                if not parse_warnings:
                    parse_warnings.append(f"{path}:{line_no}: {exc.msg}")
                elif len(parse_warnings) < 5:
                    parse_warnings.append(f"{path}:{line_no}: {exc.msg}")
                continue
            text = json.dumps(row, ensure_ascii=False)
            keys = keywords_from_text(text)
            if not keys:
                continue
            seen += 1
            source_id = str(row.get("id") or row.get("session_id") or f"{path.name}:{line_no}")
            examples.append(
                {
                    "id": f"obs-{seen:04d}",
                    "task_type": "agent_instructions_improver",
                    "task": (
                        "Audit a redacted local observation that touched agent instructions. "
                        "Recommend durable shared guidance only when repository evidence supports it."
                    ),
                    "repository_context": (
                        "Redacted observation metadata. Matched themes: "
                        f"{', '.join(keys)}. Source id: {source_id}."
                    ),
                    "current_instruction_excerpt": (
                        "Raw session text is intentionally omitted. Use the matched themes as "
                        "context, and avoid inventing repository facts."
                    ),
                    "expected": {
                        "must_find": [
                            "evidence",
                            "AGENTS.md" if "AGENTS.md" in keys else "instruction",
                        ],
                        "must_not_claim": [
                            "Claude is required",
                            "OpenAI API key is required",
                            "Qwen is required",
                        ],
                        "must_not_do": [
                            "expose raw session text",
                            "rewrite unrelated files",
                        ],
                    },
                }
            )
            if len(examples) >= limit:
                return examples, seen, parse_warnings
    return examples, seen, parse_warnings


def split_examples(examples: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if not examples:
        return {"train": [], "val": [], "test": []}
    train_count = max(1, int(len(examples) * 0.6))
    val_count = max(1, int(len(examples) * 0.2)) if len(examples) >= 3 else 0
    if train_count + val_count >= len(examples):
        train_count = max(1, len(examples) - 1)
        val_count = 0 if len(examples) < 3 else 1
    return {
        "train": examples[:train_count],
        "val": examples[train_count : train_count + val_count],
        "test": examples[train_count + val_count :],
    }


def cmd_score_fixture(args: argparse.Namespace) -> int:
    fixture = Path(args.fixture or FIXTURE_PATH)
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
    else:
        items = [payload]
    scores = [
        {
            "id": item.get("id", f"fixture-{index:03d}"),
            "score": score_response(item.get("response", ""), item.get("expected") or {}),
        }
        for index, item in enumerate(items, 1)
    ]
    print(json.dumps({"fixture": str(fixture), "scores": scores}, indent=2, sort_keys=True))
    return 0 if all(item["score"]["hard"] == 1 for item in scores) else 1


def cmd_curate(args: argparse.Namespace) -> int:
    limit = max(1, int(args.limit))
    observed, source_candidates, parse_warnings = curated_from_observations(limit)
    examples = (observed + default_examples())[:limit]
    splits = split_examples(examples)
    print(f"[curate] source_candidates={source_candidates}")
    print(f"[curate] parse_warnings={len(parse_warnings)}")
    if parse_warnings:
        print(f"[curate] first_parse_warning={parse_warnings[0]}")
    print(f"[curate] selected={len(examples)} limit={limit}")
    print(
        "[curate] split_sizes="
        f"train:{len(splits['train'])} val:{len(splits['val'])} test:{len(splits['test'])}"
    )
    if examples:
        print(f"[curate] sample_id={examples[0]['id']}")
    if args.dry_run:
        print("[curate] dry-run: no files written")
        return 0

    for split, items in splits.items():
        split_dir = DATA_DIR / split
        split_dir.mkdir(parents=True, exist_ok=True)
        (split_dir / "items.json").write_text(
            json.dumps(items, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(f"[curate] wrote redacted split data under {DATA_DIR}")
    return 0


def ensure_tool(name: str) -> str:
    if ("/" in name or name != "codex") and os.environ.get(TRUST_CODEX_EXEC_ENV) != "1":
        raise SystemExit(
            f"custom CODEX_EXEC_PATH requires {TRUST_CODEX_EXEC_ENV}=1 after reviewing the executable: {name}"
        )
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"required tool not found on PATH: {name}")
    return path


def check_codex(prefix: str = "[prepare]") -> None:
    ensure_tool(os.environ.get("CODEX_EXEC_PATH", "codex"))
    proc = run([os.environ.get("CODEX_EXEC_PATH", "codex"), "--version"], capture=True)
    version = (proc.stdout or proc.stderr).strip().splitlines()[0]
    print(f"{prefix} codex={version}")


def codex_home_path() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def probe_writable_dir(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".skillopt-write-probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    return True, "writable"


def codex_home_diagnostics(prefix: str = "[doctor-codex]") -> bool:
    check_codex(prefix=prefix)
    home = codex_home_path()
    writable, detail = probe_writable_dir(home)
    print(f"{prefix} CODEX_HOME={home}")
    print(f"{prefix} codex_home_writable={str(writable).lower()} ({detail})")
    if not writable:
        print(
            f"{prefix} live codex_exec runs need write access to Codex state; "
            "run outside the restricted sandbox or use an approved escalation."
        )
    return writable


def check_uv() -> None:
    ensure_tool("uv")
    proc = run(["uv", "--version"], capture=True)
    print(f"[prepare] {proc.stdout.strip()}")


def check_python_312() -> None:
    UV_CACHE.mkdir(parents=True, exist_ok=True)
    proc = run(
        ["uv", "--cache-dir", str(UV_CACHE), "python", "list", "--only-installed"],
        capture=True,
        check=False,
    )
    if proc.returncode != 0:
        print("[prepare] python-3.12=unknown (uv could not list installed interpreters)")
        return
    found = any(line.split()[0].startswith("cpython-3.12") for line in proc.stdout.splitlines())
    status = "installed" if found else "not-installed-yet"
    print(f"[prepare] python-3.12={status}")


def copy_overlay() -> None:
    if not SKILLOPT_CHECKOUT.exists():
        raise SystemExit(f"SkillOpt checkout not found: {SKILLOPT_CHECKOUT}")
    shutil.copytree(OVERLAY_DIR, SKILLOPT_CHECKOUT, dirs_exist_ok=True)
    config_dest = SKILLOPT_CHECKOUT / "configs" / "agent_instructions_improver" / "codex_only.yaml"
    config_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG_SRC, config_dest)


def replace_or_already(text: str, old: str, new: str, marker: str) -> tuple[str, bool]:
    if marker in text:
        return text, False
    if old not in text:
        raise RuntimeError(f"patch anchor not found: {old[:80]!r}")
    return text.replace(old, new, 1), True


def is_backend_branch(node: ast.If, backend: str) -> bool:
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Call)
        and isinstance(test.left.func, ast.Name)
        and test.left.func.id == "get_optimizer_backend"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == backend
    )


def insert_optimizer_dispatch(
    text: str,
    *,
    function_name: str,
    marker: str,
    call_expr: str,
) -> str:
    if marker in text:
        return text
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise RuntimeError(f"cannot parse SkillOpt __init__.py: {exc}") from exc
    target = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        ),
        None,
    )
    if target is None:
        raise RuntimeError(f"target function not found: {function_name}")
    branch = next(
        (
            node
            for node in target.body
            if isinstance(node, ast.If) and is_backend_branch(node, "claude_chat")
        ),
        None,
    )
    if branch is None:
        raise RuntimeError(f"claude_chat dispatch branch not found for {function_name}")
    lines = text.splitlines(keepends=True)
    branch_line = lines[branch.lineno - 1]
    indent = branch_line[: len(branch_line) - len(branch_line.lstrip())]
    insert = f'{indent}if get_optimizer_backend() == "codex_chat":\n{indent}    {call_expr}\n'
    lines.insert(branch.lineno - 1, insert)
    updated = "".join(lines)
    if marker not in updated:
        raise RuntimeError(f"codex_chat dispatch insertion failed for {function_name}")
    return updated


def patch_skillopt_checkout() -> None:
    common_path = SKILLOPT_CHECKOUT / "skillopt" / "model" / "common.py"
    backend_path = SKILLOPT_CHECKOUT / "skillopt" / "model" / "backend_config.py"
    init_path = SKILLOPT_CHECKOUT / "skillopt" / "model" / "__init__.py"
    train_path = SKILLOPT_CHECKOUT / "scripts" / "train.py"

    for path in (common_path, backend_path, init_path, train_path):
        if not path.exists():
            raise SystemExit(f"expected SkillOpt file missing: {path}")

    common = common_path.read_text(encoding="utf-8")
    if '"codex_chat": "gpt-5-codex"' not in common:
        common, _ = replace_or_already(
            common,
            '"codex_exec": "gpt-4o",',
            '"codex_exec": "gpt-4o",\n    "codex_chat": "gpt-5-codex",\n    "codex_optimizer_exec": "gpt-5-codex",',
            '"codex_chat": "gpt-5-codex"',
        )
    if '"codex_optimizer_exec": "codex_chat"' not in common:
        common, _ = replace_or_already(
            common,
            '"codex_exec": "codex_exec",',
            '"codex_exec": "codex_exec",\n    "codex_chat": "codex_chat",\n    "codex_optimizer_exec": "codex_chat",',
            '"codex_optimizer_exec": "codex_chat"',
        )
    if '"codex_chat": "gpt-5-codex"' in common or '"codex_optimizer_exec": "codex_chat"' in common:
        common_path.write_text(common, encoding="utf-8")

    backend = backend_path.read_text(encoding="utf-8")
    optimizer_set = '{"openai_chat", "claude_chat", "qwen_chat", "minimax_chat"}'
    optimizer_set_codex = (
        '{"openai_chat", "claude_chat", "qwen_chat", "minimax_chat", "codex_chat"}'
    )
    if optimizer_set in backend:
        backend = backend.replace(optimizer_set, optimizer_set_codex)
    if (
        "Supported values are 'openai_chat', 'claude_chat', 'qwen_chat', and 'minimax_chat'."
        in backend
    ):
        backend = backend.replace(
            "Supported values are 'openai_chat', 'claude_chat', 'qwen_chat', and 'minimax_chat'.",
            "Supported values are 'openai_chat', 'claude_chat', 'qwen_chat', 'minimax_chat', and 'codex_chat'.",
        )
    backend_path.write_text(backend, encoding="utf-8")

    init = init_path.read_text(encoding="utf-8")
    if "codex_chat_backend" not in init:
        init, _ = replace_or_already(
            init,
            "from skillopt.model import qwen_backend as _qwen",
            "from skillopt.model import qwen_backend as _qwen\nfrom skillopt.model import codex_chat_backend as _codex_optimizer",
            "codex_chat_backend",
        )
    init = insert_optimizer_dispatch(
        init,
        function_name="chat_optimizer",
        marker="return _codex_optimizer.chat_optimizer(",
        call_expr=(
            "return _codex_optimizer.chat_optimizer("
            "system=system, user=user, max_completion_tokens=max_completion_tokens, "
            "retries=retries, stage=stage, reasoning_effort=reasoning_effort, timeout=timeout)"
        ),
    )
    init = insert_optimizer_dispatch(
        init,
        function_name="chat_optimizer_messages",
        marker="return _codex_optimizer.chat_optimizer_messages(",
        call_expr=(
            "return _codex_optimizer.chat_optimizer_messages("
            "messages=messages, max_completion_tokens=max_completion_tokens, retries=retries, "
            "stage=stage, reasoning_effort=reasoning_effort, tools=tools, "
            "tool_choice=tool_choice, return_message=return_message, timeout=timeout)"
        ),
    )
    if "_codex_optimizer.get_token_summary()" not in init:
        init, _ = replace_or_already(
            init,
            "minimax_summary = _minimax.get_token_summary()",
            (
                "codex_summary = _codex_optimizer.get_token_summary()\n"
                "    for stage, values in codex_summary.items():\n"
                '        if stage == "_total":\n'
                "            continue\n"
                "        if stage not in summary:\n"
                "            summary[stage] = values\n"
                "            continue\n"
                '        summary[stage]["calls"] += values["calls"]\n'
                '        summary[stage]["prompt_tokens"] += values["prompt_tokens"]\n'
                '        summary[stage]["completion_tokens"] += values["completion_tokens"]\n'
                '        summary[stage]["total_tokens"] += values["total_tokens"]\n'
                "    minimax_summary = _minimax.get_token_summary()"
            ),
            "_codex_optimizer.get_token_summary()",
        )
    if "_codex_optimizer.reset_token_tracker()" not in init:
        init, _ = replace_or_already(
            init,
            "_minimax.reset_token_tracker()",
            "_minimax.reset_token_tracker()\n    _codex_optimizer.reset_token_tracker()",
            "_codex_optimizer.reset_token_tracker()",
        )
    if "_codex_optimizer.set_optimizer_deployment(deployment)" not in init:
        init, _ = replace_or_already(
            init,
            "_qwen.set_optimizer_deployment(deployment)",
            (
                "_qwen.set_optimizer_deployment(deployment)\n"
                "    _codex_optimizer.set_optimizer_deployment(deployment)"
            ),
            "_codex_optimizer.set_optimizer_deployment(deployment)",
        )
    required_init_markers = [
        "codex_chat_backend",
        "return _codex_optimizer.chat_optimizer(",
        "return _codex_optimizer.chat_optimizer_messages(",
        "_codex_optimizer.get_token_summary()",
        "_codex_optimizer.reset_token_tracker()",
        "_codex_optimizer.set_optimizer_deployment(deployment)",
    ]
    missing_init_markers = [marker for marker in required_init_markers if marker not in init]
    if missing_init_markers:
        raise RuntimeError(f"SkillOpt __init__.py patch incomplete: {missing_init_markers}")
    init_path.write_text(init, encoding="utf-8")

    train = train_path.read_text(encoding="utf-8")
    if '"agent_instructions_improver"' not in train:
        anchor = (
            "    try:\n"
            "        from skillopt.envs.searchqa.adapter import SearchQAAdapter\n"
            '        _ENV_REGISTRY["searchqa"] = SearchQAAdapter\n'
            "    except ImportError:\n"
            "        pass\n"
        )
        insert = anchor + (
            "    try:\n"
            "        from skillopt.envs.agent_instructions_improver.adapter import AgentInstructionsImproverAdapter\n"
            '        _ENV_REGISTRY["agent_instructions_improver"] = AgentInstructionsImproverAdapter\n'
            "    except ImportError:\n"
            "        pass\n"
        )
        if anchor not in train:
            raise RuntimeError("patch anchor not found for scripts/train.py env registry")
        train = train.replace(anchor, insert, 1)
        train_path.write_text(train, encoding="utf-8")

    print("[prepare] patched SkillOpt backend dispatch for codex_chat")


def cmd_prepare(args: argparse.Namespace) -> int:
    check_codex()
    check_uv()
    check_python_312()
    if args.check:
        print("[prepare] check-only: no clone or patch performed")
        return 0

    SKILLOPT_ROOT.mkdir(parents=True, exist_ok=True)
    if not SKILLOPT_CHECKOUT.exists():
        run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/microsoft/SkillOpt.git",
                str(SKILLOPT_CHECKOUT),
            ]
        )
    else:
        print(f"[prepare] using existing checkout: {SKILLOPT_CHECKOUT}")
    if args.reinstall:
        print("[prepare] --reinstall is a legacy no-op; SkillOpt is executed through uv run")
    copy_overlay()
    patch_skillopt_checkout()
    print(f"[prepare] ready: {SKILLOPT_CHECKOUT}")
    return 0


def codex_only_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if (
            (key in SAFE_ENV_KEYS or any(key.startswith(prefix) for prefix in SAFE_ENV_PREFIXES))
            and key not in BANNED_ENV_KEYS
            and not any(key.startswith(prefix) for prefix in BANNED_ENV_PREFIXES)
        )
    }
    env.update(
        {
            "OPTIMIZER_BACKEND": "codex_chat",
            "TARGET_BACKEND": "codex_exec",
            "CODEX_EXEC_PATH": os.environ.get("CODEX_EXEC_PATH", "codex")
            if os.environ.get(TRUST_CODEX_EXEC_ENV) == "1"
            else "codex",
            "CODEX_EXEC_SANDBOX": "workspace-write",
            "CODEX_EXEC_APPROVAL_POLICY": "never",
            "CODEX_EXEC_NETWORK_ACCESS": "false",
            "CODEX_OPTIMIZER_OUTPUT_ROOT": str(CODEX_OPTIMIZER_OUTPUT_ROOT),
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env


def ensure_prepared_for_train() -> None:
    if not SKILLOPT_CHECKOUT.exists():
        raise SystemExit(
            "SkillOpt is not prepared. Run: "
            "uv --cache-dir .skillopt/uv-cache run --python 3.12 python "
            "scripts/skillopt_agent_instructions.py prepare"
        )
    config_dest = SKILLOPT_CHECKOUT / "configs" / "agent_instructions_improver" / "codex_only.yaml"
    if not config_dest.exists():
        copy_overlay()
        patch_skillopt_checkout()


def data_is_ready() -> bool:
    return all((DATA_DIR / split / "items.json").exists() for split in ("train", "val", "test"))


def train_command(args: argparse.Namespace) -> list[str]:
    out_root = Path(args.out_root or OUTPUT_ROOT / "codex-only-pilot")
    return uv_python_cmd(
        "scripts/train.py",
        "--config",
        "configs/agent_instructions_improver/codex_only.yaml",
        "--split_dir",
        str(DATA_DIR),
        "--optimizer_backend",
        "codex_chat",
        "--target_backend",
        "codex_exec",
        "--num_epochs",
        str(args.num_epochs),
        "--batch_size",
        str(args.batch_size),
        "--workers",
        str(args.workers),
        "--limit",
        str(args.limit),
        "--train_size",
        str(args.train_size),
        "--max_steps",
        str(args.max_steps),
        "--steps_per_epoch",
        str(args.steps_per_epoch),
        "--out_root",
        str(out_root),
    )


def resolve_run_root(raw_path: str = "") -> Path | None:
    if raw_path:
        return Path(raw_path)
    candidates = [
        path for path in OUTPUT_ROOT.glob("*") if path.is_dir() and (path / "summary.json").exists()
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_run(run_root: Path, *, show_first_traceback: bool = False) -> tuple[int, int]:
    summary_path = run_root / "summary.json"
    if not summary_path.exists():
        print(f"[inspect-run] missing summary.json: {run_root}")
        return 1, 0

    summary = load_json_file(summary_path)
    tracebacks = sorted(run_root.glob("**/traceback.txt"))
    optimizer_traces = sorted(CODEX_OPTIMIZER_OUTPUT_ROOT.glob("*/metadata.json"))
    token_summary = summary.get("token_summary") or {}
    total_tokens = (token_summary.get("_total") or {}).get("total_tokens", 0)
    total_calls = (token_summary.get("_total") or {}).get("calls", 0)
    rollout_calls = (token_summary.get("rollout") or {}).get("calls", 0)
    analyst_calls = (token_summary.get("analyst") or {}).get("calls", 0)

    print(f"[inspect-run] run={run_root}")
    print(f"[inspect-run] tracebacks={len(tracebacks)}")
    print(f"[inspect-run] optimizer_traces={len(optimizer_traces)}")
    print(
        "[inspect-run] selection="
        f"baseline:{summary.get('baseline_selection_hard')} "
        f"best:{summary.get('best_selection_hard')}"
    )
    print(
        "[inspect-run] test="
        f"hard:{summary.get('test_hard')} soft:{summary.get('test_soft')} "
        f"delta:{summary.get('test_delta_hard')}"
    )
    print(
        "[inspect-run] steps="
        f"{summary.get('total_steps')} accepts:{summary.get('total_accepts')} "
        f"rejects:{summary.get('total_rejects')} skips:{summary.get('total_skips')}"
    )
    print(
        "[inspect-run] tokens="
        f"total:{total_tokens} calls:{total_calls} "
        f"rollout_calls:{rollout_calls} analyst_calls:{analyst_calls}"
    )
    status = "blocked" if tracebacks else "ready"
    print(f"[inspect-run] status={status}")

    if show_first_traceback and tracebacks:
        first = tracebacks[0]
        print(f"[inspect-run] first_traceback={first}")
        lines = first.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[:40]:
            print(line)

    return 0, len(tracebacks)


def cmd_train_codex(args: argparse.Namespace) -> int:
    check_codex(prefix="[train-codex]")
    env = codex_only_env()
    cmd = train_command(args)
    print("[train-codex] env=OPTIMIZER_BACKEND=codex_chat TARGET_BACKEND=codex_exec")
    print("[train-codex] codex_exec=workspace-write approvals=never network=false")
    print(f"[train-codex] command={' '.join(cmd)}")
    if args.dry_run:
        print("[train-codex] dry-run: no model calls performed")
        return 0
    if not args.allow_readonly_codex_home and not codex_home_diagnostics(prefix="[train-codex]"):
        return 2

    ensure_prepared_for_train()
    if not data_is_ready():
        print("[train-codex] curated data missing; writing default redacted split")
        curate_args = argparse.Namespace(limit=args.limit, dry_run=False)
        cmd_curate(curate_args)
    proc = run(train_command(args), cwd=SKILLOPT_CHECKOUT, env=env, check=False)
    out_root = Path(args.out_root or OUTPUT_ROOT / "codex-only-pilot")
    inspect_code, tracebacks = summarize_run(
        out_root,
        show_first_traceback=args.show_first_traceback,
    )
    if proc.returncode != 0:
        return proc.returncode
    if inspect_code != 0:
        return inspect_code
    if tracebacks:
        return 1
    return 0


def cmd_doctor_codex(args: argparse.Namespace) -> int:
    writable = codex_home_diagnostics()
    return 0 if writable or not args.strict else 1


def cmd_inspect_run(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args.run_root)
    if run_root is None:
        print("[inspect-run] no run with summary.json found under .skillopt/outputs")
        return 1
    code, tracebacks = summarize_run(
        run_root,
        show_first_traceback=args.show_first_traceback,
    )
    if code != 0:
        return code
    if args.fail_on_tracebacks and tracebacks:
        return 1
    return 0


def newest_best_skill() -> Path | None:
    candidates = sorted(
        OUTPUT_ROOT.glob("*/best_skill.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) == 3:
            return f"---\n{parts[1]}---\n", parts[2]
    return "", text


def preserve_current_frontmatter(current: str, candidate: str) -> str:
    current_frontmatter, _ = split_frontmatter(current)
    _, candidate_body = split_frontmatter(candidate)
    if not current_frontmatter:
        return candidate
    return current_frontmatter + "\n" + candidate_body.lstrip()


def frontmatter_values(frontmatter: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip("'\"")
    return values


def cmd_promote(args: argparse.Namespace) -> int:
    best = Path(args.best_skill) if args.best_skill else newest_best_skill()
    if not best or not best.exists():
        print("[promote] no best_skill.md found under .skillopt/outputs; nothing to compare")
        return 0

    current = SKILL_PATH.read_text(encoding="utf-8")
    candidate_raw = best.read_text(encoding="utf-8")
    candidate_frontmatter, _ = split_frontmatter(candidate_raw)
    if candidate_frontmatter:
        values = frontmatter_values(candidate_frontmatter)
        if values.get("name") != "agent-instructions-improver":
            print(
                f"[promote] candidate frontmatter name mismatch: {values.get('name')!r}",
                file=sys.stderr,
            )
            return 1
    candidate = preserve_current_frontmatter(current, candidate_raw)
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        candidate.splitlines(keepends=True),
        fromfile=str(SKILL_PATH),
        tofile=str(best),
    )
    print("".join(diff) or "[promote] no diff")
    if args.dry_run or not args.apply:
        print("[promote] dry-run: production SKILL.md not changed")
        return 0

    SKILL_PATH.write_text(candidate, encoding="utf-8")
    print(f"[promote] applied {best} -> {SKILL_PATH}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    score = sub.add_parser("score-fixture", help="score the deterministic fixture")
    score.add_argument("--fixture", default=str(FIXTURE_PATH))
    score.set_defaults(func=cmd_score_fixture)

    curate = sub.add_parser("curate", help="build redacted train/val/test examples")
    curate.add_argument("--dry-run", action="store_true")
    curate.add_argument("--limit", type=int, default=20)
    curate.set_defaults(func=cmd_curate)

    prepare = sub.add_parser("prepare", help="prepare local SkillOpt checkout")
    prepare.add_argument(
        "--check", action="store_true", help="check tools without cloning/installing"
    )
    prepare.add_argument(
        "--reinstall", action="store_true", help="legacy no-op; kept for old command lines"
    )
    prepare.set_defaults(func=cmd_prepare)

    train = sub.add_parser("train-codex", help="run the Codex-only pilot")
    train.add_argument("--dry-run", action="store_true")
    train.add_argument("--num-epochs", type=int, default=1)
    train.add_argument("--batch-size", type=int, default=4)
    train.add_argument("--workers", type=int, default=1)
    train.add_argument("--limit", type=int, default=4)
    train.add_argument("--train-size", type=int, default=4)
    train.add_argument("--max-steps", type=int, default=1)
    train.add_argument("--steps-per-epoch", type=int, default=1)
    train.add_argument("--out-root", default="")
    train.add_argument("--allow-readonly-codex-home", action="store_true")
    train.add_argument("--show-first-traceback", action="store_true")
    train.set_defaults(func=cmd_train_codex)

    doctor = sub.add_parser("doctor-codex", help="check local Codex CLI live-run readiness")
    doctor.add_argument(
        "--strict", action="store_true", help="exit 1 when Codex state is not writable"
    )
    doctor.set_defaults(func=cmd_doctor_codex)

    inspect = sub.add_parser("inspect-run", help="summarize a SkillOpt run output directory")
    inspect.add_argument(
        "--run-root", default="", help="default: newest .skillopt run with summary.json"
    )
    inspect.add_argument("--fail-on-tracebacks", action="store_true")
    inspect.add_argument("--show-first-traceback", action="store_true")
    inspect.set_defaults(func=cmd_inspect_run)

    promote = sub.add_parser("promote", help="compare or apply a best_skill.md candidate")
    promote.add_argument("--dry-run", action="store_true")
    promote.add_argument("--apply", action="store_true")
    promote.add_argument("--best-skill", default="")
    promote.set_defaults(func=cmd_promote)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
