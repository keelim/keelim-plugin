#!/usr/bin/env python3
"""uv-only Codex SkillOpt runner for all keelim-plugin skills."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
EVAL_DIR = REPO_ROOT / "evals" / "skillopt" / "plugin-skill-improver"
OVERLAY_DIR = EVAL_DIR / "overlays"
CONFIG_SRC = EVAL_DIR / "configs" / "plugin_skill_improver" / "codex_only.yaml"
CODEX_BACKEND_SRC = (
    REPO_ROOT
    / "evals"
    / "skillopt"
    / "agent-instructions-improver"
    / "overlays"
    / "skillopt"
    / "model"
    / "codex_chat_backend.py"
)
SKILLOPT_ROOT = REPO_ROOT / ".skillopt"
SKILLOPT_CHECKOUT = SKILLOPT_ROOT / "SkillOpt"
UV_CACHE = SKILLOPT_ROOT / "uv-cache"
DATA_ROOT = SKILLOPT_ROOT / "data" / "plugin-skill-improver-v1"
OUTPUT_ROOT = SKILLOPT_ROOT / "outputs"
CODEX_OPTIMIZER_OUTPUT_ROOT = OUTPUT_ROOT / "codex-optimizer"
QUICK_VALIDATE_ENV = "KEELIM_PLUGIN_QUICK_VALIDATE"
TRUST_CODEX_EXEC_ENV = "KEELIM_PLUGIN_TRUST_CODEX_EXEC"
EXPECTED_SKILLOPT_REV = "ee9931ec017cd8d9ce7caab272983e268258ddf5"
SUBPROCESS_TIMEOUT_ENV = "KEELIM_PLUGIN_SUBPROCESS_TIMEOUT_SECONDS"

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


@dataclass(frozen=True)
class SkillInfo:
    name: str
    path: Path
    text: str
    frontmatter: dict[str, str]
    resource_dirs: tuple[str, ...]


@dataclass
class GateResult:
    skill: str
    status: str
    candidate: str | None
    reasons: list[str]

    def as_json(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "status": self.status,
            "candidate": self.candidate,
            "reasons": self.reasons,
        }


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def default_subprocess_timeout() -> int:
    raw = os.environ.get(SUBPROCESS_TIMEOUT_ENV, "1800")
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit(f"{SUBPROCESS_TIMEOUT_ENV} must be an integer number of seconds") from None
    if value <= 0:
        raise SystemExit(f"{SUBPROCESS_TIMEOUT_ENV} must be greater than zero")
    return value


def run(
    cmd: list[str],
    *,
    cwd: Path = REPO_ROOT,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    timeout_seconds = timeout or default_subprocess_timeout()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=capture,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        if exc.stdout:
            eprint(str(exc.stdout).rstrip())
        if exc.stderr:
            eprint(str(exc.stderr).rstrip())
        raise SystemExit(f"command timed out after {timeout_seconds}s: {' '.join(cmd)}") from exc
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


def uv_python_with_cmd(package: str, *python_args: str) -> list[str]:
    return [
        "uv",
        "--cache-dir",
        str(UV_CACHE),
        "run",
        "--python",
        "3.12",
        "--with",
        package,
        "python",
        *python_args,
    ]


def quick_validate_path() -> Path | None:
    configured = os.environ.get(QUICK_VALIDATE_ENV, "")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend(
        [
            Path.home()
            / ".codex"
            / "skills"
            / ".system"
            / "skill-creator"
            / "scripts"
            / "quick_validate.py",
            Path.home()
            / ".agents"
            / "skills"
            / ".system"
            / "skill-creator"
            / "scripts"
            / "quick_validate.py",
        ]
    )
    return next((path for path in candidates if path.is_file()), None)


def ensure_tool(name: str) -> str:
    if ("/" in name or name != "codex") and os.environ.get(TRUST_CODEX_EXEC_ENV) != "1":
        raise SystemExit(
            f"custom CODEX_EXEC_PATH requires {TRUST_CODEX_EXEC_ENV}=1 after reviewing the executable: {name}"
        )
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"required tool not found on PATH: {name}")
    return path


def check_uv(prefix: str = "[prepare]") -> None:
    ensure_tool("uv")
    proc = run(["uv", "--version"], capture=True)
    print(f"{prefix} {proc.stdout.strip()}")


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


def parse_frontmatter(text: str) -> tuple[dict[str, str], str, str]:
    if not text.startswith("---\n"):
        return {}, "", text
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return {}, "", text
    raw = f"---\n{parts[1]}---\n"
    values: dict[str, str] = {}
    for line in parts[1].splitlines():
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip("'\"")
    return values, raw, parts[2]


def skill_names() -> list[str]:
    return [
        path.name
        for path in sorted(SKILLS_DIR.iterdir())
        if path.is_dir() and (path / "SKILL.md").exists()
    ]


def select_skill_names(raw: str | None) -> list[str]:
    names = skill_names()
    if raw is None or raw in ("", "all"):
        return names
    requested = [item.strip() for item in raw.split(",") if item.strip()]
    missing = [item for item in requested if item not in names]
    if missing:
        raise SystemExit(f"unknown skill(s): {', '.join(missing)}")
    return requested


def load_skill(name: str) -> SkillInfo:
    path = SKILLS_DIR / name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    frontmatter, _, _ = parse_frontmatter(text)
    resources = tuple(
        resource
        for resource in ("references", "scripts", "assets")
        if (SKILLS_DIR / name / resource).is_dir()
    )
    return SkillInfo(
        name=name,
        path=path,
        text=text,
        frontmatter=frontmatter,
        resource_dirs=resources,
    )


def excerpt(text: str, limit: int = 1800) -> str:
    compact = "\n".join(line.rstrip() for line in text.strip().splitlines())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "\n...[redacted]"


def resource_inventory(skill: SkillInfo) -> str:
    if not skill.resource_dirs:
        return "No bundled references, scripts, or assets."
    lines = []
    for dirname in skill.resource_dirs:
        root = SKILLS_DIR / skill.name / dirname
        files = sorted(
            path.relative_to(SKILLS_DIR / skill.name) for path in root.rglob("*") if path.is_file()
        )
        preview = ", ".join(str(path) for path in files[:8])
        if len(files) > 8:
            preview += f", ... ({len(files)} files)"
        lines.append(f"{dirname}/: {preview or 'empty'}")
    return "\n".join(lines)


def readme_description(skill_name: str) -> str:
    readme = REPO_ROOT / "README.md"
    if not readme.exists():
        return ""
    pattern = re.compile(rf"^-\s+`{re.escape(skill_name)}`:\s*(.+)$", re.MULTILINE)
    match = pattern.search(readme.read_text(encoding="utf-8"))
    return match.group(1).strip() if match else ""


def expected_for(skill: SkillInfo, *must_find: str) -> dict[str, list[str]]:
    required = [skill.name, *must_find]
    for resource in skill.resource_dirs:
        if resource in must_find:
            continue
    return {
        "must_find": required,
        "must_not_claim": [
            "OpenAI API key is required",
            "Claude is required",
            "Qwen is required",
            "Azure key is required",
        ],
        "must_not_do": [
            "delete bundled resources",
            "discard frontmatter",
            "rewrite unrelated files",
            "run python3 directly",
        ],
    }


def examples_for_skill(skill: SkillInfo) -> list[dict[str, Any]]:
    description = skill.frontmatter.get("description") or readme_description(skill.name)
    resources = resource_inventory(skill)
    context = (
        f"Skill: {skill.name}. Description: {description}. "
        "This is one of the local plugin skills shared by Codex and Claude."
    )
    resource_terms = list(skill.resource_dirs)
    resource_clause = ", ".join(resource_terms) if resource_terms else "no bundled resources"
    return [
        {
            "id": f"{skill.name}-frontmatter-001",
            "task_type": "plugin_skill_improver",
            "skill_name": skill.name,
            "task": (
                "Review a candidate update. Explicitly mention the skill name, "
                "frontmatter, and whether the description remains a useful trigger."
            ),
            "repository_context": context,
            "current_skill_excerpt": excerpt(skill.text),
            "resource_inventory": resources,
            "expected": expected_for(skill, "frontmatter", "description"),
        },
        {
            "id": f"{skill.name}-resources-002",
            "task_type": "plugin_skill_improver",
            "skill_name": skill.name,
            "task": (
                "Identify what bundled resources must be preserved during promotion. "
                f"The resource inventory is: {resource_clause}."
            ),
            "repository_context": context,
            "current_skill_excerpt": excerpt(skill.text),
            "resource_inventory": resources,
            "expected": expected_for(skill, "resource"),
        },
        {
            "id": f"{skill.name}-concise-003",
            "task_type": "plugin_skill_improver",
            "skill_name": skill.name,
            "task": (
                "Recommend a concise SKILL.md improvement while preserving the "
                "workflow's useful degree of freedom."
            ),
            "repository_context": context,
            "current_skill_excerpt": excerpt(skill.text),
            "resource_inventory": resources,
            "expected": expected_for(skill, "concise", "SKILL.md"),
        },
        {
            "id": f"{skill.name}-validation-004",
            "task_type": "plugin_skill_improver",
            "skill_name": skill.name,
            "task": "Name the validation commands or checks that should protect this skill update.",
            "repository_context": context,
            "current_skill_excerpt": excerpt(skill.text),
            "resource_inventory": resources,
            "expected": expected_for(skill, "validate", "command"),
        },
        {
            "id": f"{skill.name}-evidence-005",
            "task_type": "plugin_skill_improver",
            "skill_name": skill.name,
            "task": "Explain how to keep the candidate grounded in repository evidence.",
            "repository_context": context,
            "current_skill_excerpt": excerpt(skill.text),
            "resource_inventory": resources,
            "expected": expected_for(skill, "evidence"),
        },
        {
            "id": f"{skill.name}-provider-drift-006",
            "task_type": "plugin_skill_improver",
            "skill_name": skill.name,
            "task": "Review the candidate for unwanted provider, API key, or model fallback drift.",
            "repository_context": context,
            "current_skill_excerpt": excerpt(skill.text),
            "resource_inventory": resources,
            "expected": expected_for(skill, "provider"),
        },
        {
            "id": f"{skill.name}-progressive-disclosure-007",
            "task_type": "plugin_skill_improver",
            "skill_name": skill.name,
            "task": "Assess whether details belong in SKILL.md or a referenced resource file.",
            "repository_context": context,
            "current_skill_excerpt": excerpt(skill.text),
            "resource_inventory": resources,
            "expected": expected_for(skill, "SKILL.md", "resource"),
        },
        {
            "id": f"{skill.name}-promotion-008",
            "task_type": "plugin_skill_improver",
            "skill_name": skill.name,
            "task": "State the final promotion decision criteria for this skill candidate.",
            "repository_context": context,
            "current_skill_excerpt": excerpt(skill.text),
            "resource_inventory": resources,
            "expected": expected_for(skill, "promotion", "criteria"),
        },
    ]


def split_examples(examples: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "train": examples[:4],
        "val": examples[4:6],
        "test": examples[6:],
    }


def data_dir_for(skill_name: str) -> Path:
    return DATA_ROOT / skill_name


def output_root_for(skill_name: str, run_id: str) -> Path:
    return OUTPUT_ROOT / skill_name / run_id


def current_run_id() -> str:
    return datetime.now(UTC).strftime("codex-tiny-%Y%m%dT%H%M%SZ")


def write_skill_data(skill: SkillInfo, *, dry_run: bool = False) -> None:
    splits = split_examples(examples_for_skill(skill))
    print(
        f"[curate] {skill.name} split_sizes="
        f"train:{len(splits['train'])} val:{len(splits['val'])} test:{len(splits['test'])}"
    )
    if dry_run:
        return
    root = data_dir_for(skill.name)
    root.mkdir(parents=True, exist_ok=True)
    (root / "initial.md").write_text(skill.text, encoding="utf-8")
    for split, items in splits.items():
        split_dir = root / split
        split_dir.mkdir(parents=True, exist_ok=True)
        (split_dir / "items.json").write_text(
            json.dumps(items, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def data_is_ready(skill_name: str) -> bool:
    root = data_dir_for(skill_name)
    return all((root / split / "items.json").exists() for split in ("train", "val", "test"))


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


def insert_optimizer_dispatch(text: str, *, function_name: str, marker: str, call_expr: str) -> str:
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
    lines.insert(
        branch.lineno - 1,
        f'{indent}if get_optimizer_backend() == "codex_chat":\n{indent}    {call_expr}\n',
    )
    updated = "".join(lines)
    if marker not in updated:
        raise RuntimeError(f"codex_chat dispatch insertion failed for {function_name}")
    return updated


def copy_overlay() -> None:
    if not SKILLOPT_CHECKOUT.exists():
        raise SystemExit(f"SkillOpt checkout not found: {SKILLOPT_CHECKOUT}")
    shutil.copytree(OVERLAY_DIR, SKILLOPT_CHECKOUT, dirs_exist_ok=True)
    model_dest = SKILLOPT_CHECKOUT / "skillopt" / "model" / "codex_chat_backend.py"
    model_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CODEX_BACKEND_SRC, model_dest)
    config_dest = SKILLOPT_CHECKOUT / "configs" / "plugin_skill_improver" / "codex_only.yaml"
    config_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG_SRC, config_dest)


def verify_skillopt_revision() -> None:
    if not SKILLOPT_CHECKOUT.exists():
        return
    proc = run(
        ["git", "-C", str(SKILLOPT_CHECKOUT), "rev-parse", "HEAD"], capture=True, check=False
    )
    current = proc.stdout.strip() if proc.returncode == 0 else ""
    expected = os.environ.get("SKILLOPT_EXPECTED_REV", EXPECTED_SKILLOPT_REV)
    if current != expected:
        raise SystemExit(
            f"SkillOpt checkout revision {current or 'unknown'} does not match pinned {expected}; "
            "review and update SKILLOPT_EXPECTED_REV only after validating upstream changes"
        )


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
    common_path.write_text(common, encoding="utf-8")

    backend = backend_path.read_text(encoding="utf-8")
    backend, _ = replace_or_already(
        backend,
        '{"openai_chat", "claude_chat", "qwen_chat", "minimax_chat"}',
        '{"openai_chat", "claude_chat", "qwen_chat", "minimax_chat", "codex_chat"}',
        '"codex_chat"',
    )
    backend, _ = replace_or_already(
        backend,
        "Supported values are 'openai_chat', 'claude_chat', 'qwen_chat', and 'minimax_chat'.",
        "Supported values are 'openai_chat', 'claude_chat', 'qwen_chat', 'minimax_chat', and 'codex_chat'.",
        "and 'codex_chat'.",
    )
    if "codex_chat" not in backend:
        raise RuntimeError("SkillOpt backend_config.py patch incomplete: codex_chat missing")
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
            "_qwen.set_optimizer_deployment(deployment)\n    _codex_optimizer.set_optimizer_deployment(deployment)",
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
    if '"plugin_skill_improver"' not in train:
        anchor = (
            "    try:\n"
            "        from skillopt.envs.agent_instructions_improver.adapter import AgentInstructionsImproverAdapter\n"
            '        _ENV_REGISTRY["agent_instructions_improver"] = AgentInstructionsImproverAdapter\n'
            "    except ImportError:\n"
            "        pass\n"
        )
        insert = anchor + (
            "    try:\n"
            "        from skillopt.envs.plugin_skill_improver.adapter import PluginSkillImproverAdapter\n"
            '        _ENV_REGISTRY["plugin_skill_improver"] = PluginSkillImproverAdapter\n'
            "    except ImportError:\n"
            "        pass\n"
        )
        if anchor not in train:
            searchqa_anchor = (
                "    try:\n"
                "        from skillopt.envs.searchqa.adapter import SearchQAAdapter\n"
                '        _ENV_REGISTRY["searchqa"] = SearchQAAdapter\n'
                "    except ImportError:\n"
                "        pass\n"
            )
            insert = searchqa_anchor + (
                "    try:\n"
                "        from skillopt.envs.plugin_skill_improver.adapter import PluginSkillImproverAdapter\n"
                '        _ENV_REGISTRY["plugin_skill_improver"] = PluginSkillImproverAdapter\n'
                "    except ImportError:\n"
                "        pass\n"
            )
            anchor = searchqa_anchor
        if anchor not in train:
            raise RuntimeError("patch anchor not found for scripts/train.py env registry")
        train = train.replace(anchor, insert, 1)
        train_path.write_text(train, encoding="utf-8")
    print("[prepare] patched SkillOpt backend dispatch and plugin_skill_improver env")


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
            "scripts/skillopt_plugin_skills.py prepare"
        )
    verify_skillopt_revision()
    config_dest = SKILLOPT_CHECKOUT / "configs" / "plugin_skill_improver" / "codex_only.yaml"
    if not config_dest.exists():
        copy_overlay()
        patch_skillopt_checkout()


def train_command(skill_name: str, args: argparse.Namespace, run_id: str) -> list[str]:
    skill_data = data_dir_for(skill_name)
    out_root = (
        (Path(args.out_root) / skill_name / run_id)
        if args.out_root
        else output_root_for(skill_name, run_id)
    )
    return uv_python_cmd(
        "scripts/train.py",
        "--config",
        "configs/plugin_skill_improver/codex_only.yaml",
        "--split_dir",
        str(skill_data),
        "--skill_init",
        str(skill_data / "initial.md"),
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


def resolve_latest_run(skill_name: str) -> Path | None:
    root = OUTPUT_ROOT / skill_name
    candidates = [
        path for path in root.glob("*") if path.is_dir() and (path / "summary.json").exists()
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_run(run_root: Path, *, show_first_traceback: bool = False) -> tuple[int, int]:
    summary_path = run_root / "summary.json"
    if not summary_path.exists():
        print(f"[inspect] missing summary.json: {run_root}")
        return 1, 0
    summary = load_json(summary_path)
    tracebacks = sorted(run_root.glob("**/traceback.txt"))
    token_summary = summary.get("token_summary") or {}
    total_tokens = (token_summary.get("_total") or {}).get("total_tokens", 0)
    total_calls = (token_summary.get("_total") or {}).get("calls", 0)
    print(f"[inspect] run={run_root}")
    print(f"[inspect] tracebacks={len(tracebacks)}")
    print(
        "[inspect] selection="
        f"baseline:{summary.get('baseline_selection_hard')} "
        f"best:{summary.get('best_selection_hard')}"
    )
    print(
        "[inspect] test="
        f"baseline_hard:{summary.get('baseline_test_hard')} "
        f"hard:{summary.get('test_hard')} "
        f"baseline_soft:{summary.get('baseline_test_soft')} "
        f"soft:{summary.get('test_soft')}"
    )
    print(
        "[inspect] steps="
        f"{summary.get('total_steps')} accepts:{summary.get('total_accepts')} "
        f"rejects:{summary.get('total_rejects')} skips:{summary.get('total_skips')}"
    )
    print(f"[inspect] tokens=total:{total_tokens} calls:{total_calls}")
    if show_first_traceback and tracebacks:
        first = tracebacks[0]
        print(f"[inspect] first_traceback={first}")
        for line in first.read_text(encoding="utf-8", errors="replace").splitlines()[:40]:
            print(line)
    return 0, len(tracebacks)


def body_line_count(text: str) -> int:
    _, _, body = parse_frontmatter(text)
    return len([line for line in body.splitlines() if line.strip()])


def validate_candidate(skill: SkillInfo, candidate_path: Path, run_root: Path) -> GateResult:
    reasons: list[str] = []
    summary_path = run_root / "summary.json"
    if not summary_path.exists():
        reasons.append("missing summary.json")
    else:
        summary = load_json(summary_path)
        baseline_hard = float(summary.get("baseline_test_hard") or 0)
        test_hard = float(summary.get("test_hard") or 0)
        baseline_soft = float(summary.get("baseline_test_soft") or 0)
        test_soft = float(summary.get("test_soft") or 0)
        if test_hard < baseline_hard:
            reasons.append(f"hard regression {test_hard} < {baseline_hard}")
        if test_soft < baseline_soft:
            reasons.append(f"soft regression {test_soft} < {baseline_soft}")
    tracebacks = sorted(run_root.glob("**/traceback.txt"))
    if tracebacks:
        reasons.append(f"tracebacks present: {len(tracebacks)}")
    if not candidate_path.exists():
        reasons.append("missing best_skill.md")
        return GateResult(skill.name, "rejected", None, reasons)

    candidate = candidate_path.read_text(encoding="utf-8")
    frontmatter, _, _ = parse_frontmatter(candidate)
    if frontmatter.get("name") != skill.name:
        reasons.append(f"frontmatter name mismatch: {frontmatter.get('name')!r}")
    if not frontmatter.get("description"):
        reasons.append("frontmatter missing description")
    current_lines = max(1, body_line_count(skill.text))
    candidate_lines = body_line_count(candidate)
    if candidate_lines < current_lines * 0.6:
        reasons.append(f"candidate too short: {candidate_lines} < 60% of {current_lines}")
    if candidate_lines > current_lines * 1.8:
        reasons.append(f"candidate too long: {candidate_lines} > 180% of {current_lines}")
    normalized = candidate.lower()
    for resource in skill.resource_dirs:
        if resource not in normalized:
            reasons.append(f"missing resource guidance: {resource}/")
    banned_execution = [
        "python3",
        ".skillopt/venv",
        "venv/bin/python",
        ".venv/bin/python",
    ]
    for snippet in banned_execution:
        if snippet in normalized:
            reasons.append(f"direct Python execution guidance present: {snippet}")
    status = "passing" if not reasons else "rejected"
    return GateResult(skill.name, status, str(candidate_path), reasons)


def newest_best_skill(run_root: Path) -> Path:
    return run_root / "best_skill.md"


def apply_candidate(skill_name: str, candidate_path: Path) -> int:
    cmd = uv_python_cmd(
        "scripts/promote_plugin_skills.py",
        "promote",
        "--skill",
        skill_name,
        "--candidate",
        str(candidate_path),
        "--apply",
    )
    proc = run(cmd, cwd=REPO_ROOT, check=False)
    return proc.returncode


def run_validators() -> int:
    checks = [uv_python_cmd("scripts/run-tests.py")]
    for cmd in checks:
        proc = run(cmd, cwd=REPO_ROOT, check=False)
        if proc.returncode != 0:
            return proc.returncode
    quick_validate = quick_validate_path()
    if quick_validate is None:
        print(
            f"[validate] quick_validate skipped: set {QUICK_VALIDATE_ENV} to the skill-creator quick_validate.py path"
        )
        return 0
    for name in skill_names():
        proc = run(
            uv_python_with_cmd("pyyaml", str(quick_validate), str(SKILLS_DIR / name)),
            cwd=REPO_ROOT,
            check=False,
        )
        if proc.returncode != 0:
            return proc.returncode
    return 0


def write_report(path: Path, results: list[GateResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "repo": str(REPO_ROOT),
        "results": [result.as_json() for result in results],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_prepare(args: argparse.Namespace) -> int:
    check_codex()
    check_uv()
    UV_CACHE.mkdir(parents=True, exist_ok=True)
    proc = run(
        ["uv", "--cache-dir", str(UV_CACHE), "python", "list", "--only-installed"],
        capture=True,
        check=False,
    )
    if proc.returncode == 0:
        found = any(line.split()[0].startswith("cpython-3.12") for line in proc.stdout.splitlines())
        print(f"[prepare] python-3.12={'installed' if found else 'not-installed-yet'}")
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
    verify_skillopt_revision()
    copy_overlay()
    patch_skillopt_checkout()
    print(f"[prepare] ready: {SKILLOPT_CHECKOUT}")
    return 0


def cmd_doctor_codex(args: argparse.Namespace) -> int:
    writable = codex_home_diagnostics()
    return 0 if writable or not args.strict else 1


def cmd_curate(args: argparse.Namespace) -> int:
    for name in select_skill_names(args.skill):
        write_skill_data(load_skill(name), dry_run=args.dry_run)
    if args.dry_run:
        print("[curate] dry-run: no files written")
    return 0


def cmd_train_codex(args: argparse.Namespace) -> int:
    skill = load_skill(args.skill)
    run_id = args.run_id or current_run_id()
    cmd = train_command(skill.name, args, run_id)
    print("[train-codex] env=OPTIMIZER_BACKEND=codex_chat TARGET_BACKEND=codex_exec")
    print("[train-codex] codex_exec=workspace-write approvals=never network=false")
    print(f"[train-codex] skill={skill.name} run_id={run_id}")
    print(f"[train-codex] command={' '.join(cmd)}")
    if args.dry_run:
        print("[train-codex] dry-run: no model calls performed")
        return 0
    if not args.allow_readonly_codex_home and not codex_home_diagnostics(prefix="[train-codex]"):
        return 2
    ensure_prepared_for_train()
    if not data_is_ready(skill.name):
        write_skill_data(skill)
    proc = run(
        cmd,
        cwd=SKILLOPT_CHECKOUT,
        env=codex_only_env(),
        check=False,
        timeout=args.timeout_seconds or None,
    )
    run_root = (
        (Path(args.out_root) / skill.name / run_id)
        if args.out_root
        else output_root_for(skill.name, run_id)
    )
    inspect_code, tracebacks = summarize_run(
        run_root, show_first_traceback=args.show_first_traceback
    )
    if proc.returncode != 0:
        return proc.returncode
    if inspect_code != 0:
        return inspect_code
    if tracebacks:
        return 1
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    skill = load_skill(args.skill)
    run_root = Path(args.run_root) if args.run_root else resolve_latest_run(skill.name)
    if run_root is None:
        print(f"[gate] {skill.name}: no run found")
        return 1
    result = validate_candidate(skill, newest_best_skill(run_root), run_root)
    print(json.dumps(result.as_json(), indent=2, ensure_ascii=False))
    return 0 if result.status == "passing" else 1


def cmd_inspect_all(args: argparse.Namespace) -> int:
    results: list[GateResult] = []
    exit_code = 0
    for name in select_skill_names(args.skill):
        run_root = resolve_latest_run(name)
        if run_root is None:
            result = GateResult(name, "missing-run", None, ["no run with summary.json"])
            results.append(result)
            print(f"[inspect-all] {name}: missing-run")
            exit_code = 1
            continue
        code, tracebacks = summarize_run(run_root, show_first_traceback=args.show_first_traceback)
        if code != 0 or (args.fail_on_tracebacks and tracebacks):
            exit_code = 1
        result = validate_candidate(load_skill(name), newest_best_skill(run_root), run_root)
        results.append(result)
        print(f"[inspect-all] {name}: {result.status} reasons={result.reasons}")
    if args.report:
        write_report(Path(args.report), results)
        print(f"[inspect-all] report={args.report}")
    return exit_code


def cmd_run_all(args: argparse.Namespace) -> int:
    check_codex(prefix="[run-all]")
    check_uv(prefix="[run-all]")
    if args.dry_run:
        for name in select_skill_names(args.skill):
            train_args = argparse.Namespace(**vars(args))
            train_args.skill = name
            train_args.run_id = args.run_id or f"dry-run-{name}"
            cmd_train_codex(train_args)
        return 0
    if not args.allow_readonly_codex_home and not codex_home_diagnostics(prefix="[run-all]"):
        return 2
    ensure_prepared_for_train()
    results: list[GateResult] = []
    exit_code = 0
    for name in select_skill_names(args.skill):
        skill = load_skill(name)
        write_skill_data(skill)
        run_id = args.run_id or current_run_id()
        train_args = argparse.Namespace(**vars(args))
        train_args.skill = name
        train_args.run_id = run_id
        train_args.allow_readonly_codex_home = True
        print(f"[run-all] training {name}")
        train_code = cmd_train_codex(train_args)
        run_root = (
            (Path(args.out_root) / name / run_id)
            if args.out_root
            else output_root_for(name, run_id)
        )
        if train_code != 0:
            result = GateResult(name, "train-failed", None, [f"train exit {train_code}"])
            results.append(result)
            exit_code = train_code or 1
            continue
        result = validate_candidate(skill, newest_best_skill(run_root), run_root)
        results.append(result)
        print(f"[run-all] gate {name}: {result.status} reasons={result.reasons}")
        if result.status == "passing" and args.apply_passing and result.candidate:
            apply_code = apply_candidate(name, Path(result.candidate))
            if apply_code != 0:
                result.status = "apply-failed"
                result.reasons.append(f"promote apply exit {apply_code}")
                exit_code = apply_code
        elif result.status != "passing":
            exit_code = 1
    if args.apply_passing:
        validate_code = run_validators()
        if validate_code != 0:
            exit_code = validate_code
    report = Path(args.report or OUTPUT_ROOT / "plugin-skill-improver-report.json")
    write_report(report, results)
    print(f"[run-all] report={report}")
    return exit_code


def add_train_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--num-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--train-size", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=1)
    parser.add_argument("--steps-per-epoch", type=int, default=1)
    parser.add_argument("--out-root", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--allow-readonly-codex-home", action="store_true")
    parser.add_argument("--show-first-traceback", action="store_true")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=0,
        help=f"override {SUBPROCESS_TIMEOUT_ENV} for each external command",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="prepare local SkillOpt checkout")
    prepare.add_argument("--check", action="store_true")
    prepare.set_defaults(func=cmd_prepare)

    doctor = sub.add_parser("doctor-codex", help="check local Codex CLI live-run readiness")
    doctor.add_argument("--strict", action="store_true")
    doctor.set_defaults(func=cmd_doctor_codex)

    curate = sub.add_parser("curate", help="build per-skill redacted splits")
    curate.add_argument("--skill", default="all")
    curate.add_argument("--dry-run", action="store_true")
    curate.set_defaults(func=cmd_curate)

    train = sub.add_parser("train-codex", help="run one skill tiny pilot")
    train.add_argument("--skill", required=True, choices=skill_names())
    train.add_argument("--dry-run", action="store_true")
    add_train_args(train)
    train.set_defaults(func=cmd_train_codex)

    gate = sub.add_parser("gate", help="evaluate one run promotion gate")
    gate.add_argument("--skill", required=True, choices=skill_names())
    gate.add_argument("--run-root", default="")
    gate.set_defaults(func=cmd_gate)

    inspect = sub.add_parser("inspect-all", help="summarize all latest skill runs")
    inspect.add_argument("--skill", default="all")
    inspect.add_argument("--fail-on-tracebacks", action="store_true")
    inspect.add_argument("--show-first-traceback", action="store_true")
    inspect.add_argument("--report", default="")
    inspect.set_defaults(func=cmd_inspect_all)

    run_all = sub.add_parser("run-all", help="run tiny pilot for every selected skill")
    run_all.add_argument("--skill", default="all")
    run_all.add_argument("--dry-run", action="store_true")
    run_all.add_argument("--apply-passing", action="store_true")
    run_all.add_argument("--report", default="")
    add_train_args(run_all)
    run_all.set_defaults(func=cmd_run_all)

    validate = sub.add_parser("validate", help="run non-live validation gates")
    validate.set_defaults(func=lambda _args: run_validators())

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
