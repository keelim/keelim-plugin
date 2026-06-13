#!/usr/bin/env python3
"""Validate keelim-plugin skill folders and Codex metadata."""

from __future__ import annotations

import argparse
import importlib
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
README = REPO_ROOT / "README.md"


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def parse_simple_yaml(text: str, source: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for line_no, raw_line in enumerate(text.splitlines(), 1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("\t"):
            raise ValueError(f"{source}:{line_no}: tabs are not supported")
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if ":" not in stripped:
            raise ValueError(f"{source}:{line_no}: expected key: value")
        key, value = stripped.split(":", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"{source}:{line_no}: empty key")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"{source}:{line_no}: invalid indentation")
        parent = stack[-1][1]
        if value.strip():
            parent[key] = parse_scalar(value)
            continue
        child: dict[str, Any] = {}
        parent[key] = child
        stack.append((indent, child))
    return root


def parse_yaml(text: str, source: Path) -> dict[str, Any]:
    try:
        yaml = importlib.import_module("yaml")
    except ImportError:
        return parse_simple_yaml(text, source)
    payload = yaml.safe_load(text) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{source}: expected a YAML mapping")
    return payload


def split_frontmatter(text: str, source: Path) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return {}, text
    return parse_yaml(parts[1], source), parts[2]


def readme_skill_names() -> set[str]:
    if not README.exists():
        return set()
    text = README.read_text(encoding="utf-8")
    section = re.split(r"^##\s+Current skills\s*$", text, flags=re.MULTILINE)
    if len(section) < 2:
        return set()
    body = re.split(r"^##\s+", section[1], maxsplit=1, flags=re.MULTILINE)[0]
    return set(re.findall(r"^-\s+`([^`]+)`", body, flags=re.MULTILINE))


def validate_codex_meta(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    meta_path = skill_dir / "agents" / "openai.yaml"
    if not meta_path.exists():
        return errors
    try:
        meta = parse_yaml(meta_path.read_text(encoding="utf-8"), meta_path)
    except Exception as exc:  # noqa: BLE001
        return [f"agents/openai.yaml parse error: {exc}"]
    interface = meta.get("interface")
    if not isinstance(interface, dict):
        return ["agents/openai.yaml missing interface mapping"]
    for field in ("display_name", "short_description", "default_prompt"):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"agents/openai.yaml interface.{field} must be a non-empty string")
    policy = meta.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            errors.append("agents/openai.yaml policy must be a mapping when present")
        else:
            allow_implicit = policy.get("allow_implicit_invocation")
            if allow_implicit is not None and not isinstance(allow_implicit, bool):
                errors.append("agents/openai.yaml policy.allow_implicit_invocation must be boolean")
    return errors


def extract_backticked_bullets(text: str) -> set[str]:
    return set(re.findall(r"^-\s+`([^`]+)`", text, flags=re.MULTILINE))


def validate_agent_instructions_improver(
    skill_dir: Path, frontmatter: dict[str, Any], body: str
) -> list[str]:
    errors: list[str] = []
    description = str(frontmatter.get("description", ""))
    if "check, audit, update, improve" in description:
        errors.append("frontmatter trigger is too broad for routing")
    if "simple file lookup" not in description:
        errors.append("frontmatter must exclude simple file lookup")
    if "head -80" in body:
        errors.append("discovery command silently truncates with head -80")
    if "greater than 80" not in body or "preview only" not in body:
        errors.append("discovery workflow missing truncation guard")

    denominators = [int(match) for match in re.findall(r"\|\s+[^|\n]+\s+\|\s+X/(\d+)\s+\|", body)]
    if not denominators:
        errors.append("quality report template missing numeric score rows")
    elif sum(denominators) != 100:
        errors.append(f"quality report score rows sum to {sum(denominators)}, expected 100")

    criteria_path = skill_dir / "references" / "quality-criteria.md"
    if criteria_path.exists():
        criteria = criteria_path.read_text(encoding="utf-8")
        if "mentally or actually" in criteria:
            errors.append("quality criteria allows mental command validation")
        if "`not run`" not in criteria:
            errors.append("quality criteria must require not-run reporting for skipped commands")
    return errors


def validate_codebase_codemap(skill_dir: Path, frontmatter: dict[str, Any], body: str) -> list[str]:
    errors: list[str] = []
    description = str(frontmatter.get("description", ""))
    if "agent needs stronger codebase orientation before editing" in description:
        errors.append("frontmatter trigger includes generic pre-edit orientation")
    if "/path/to/codebase-codemap" in body:
        errors.append("workflow contains non-copyable codebase-codemap placeholder path")
    if "docs/CODEMAPS/agent-codemap.md" in body:
        errors.append("verification path must use project-named codemap output")

    schema_path = skill_dir / "references" / "codemap-schema.md"
    if schema_path.exists():
        schema = schema_path.read_text(encoding="utf-8")
        marker = "Include these sections when editing manually:"
        manual_block = body.split(marker, 1)[1] if marker in body else ""
        required = extract_backticked_bullets(schema)
        manual = extract_backticked_bullets(manual_block)
        missing = sorted(required - manual)
        if missing:
            errors.append(
                "manual section list missing schema required sections: " + ", ".join(missing)
            )
    return errors


def validate_html_report_generator(skill_dir: Path, body: str) -> list[str]:
    errors: list[str] = []
    if "/Users/" in body:
        errors.append("verification commands must not hardcode a user home path")
    schema_path = skill_dir / "references" / "report-schema.md"
    if schema_path.exists():
        schema = schema_path.read_text(encoding="utf-8")
        if "- `links`:" not in schema:
            errors.append("report schema core fields must document links")
    return errors


def validate_jira_ticket_desk(skill_dir: Path, body: str) -> list[str]:
    errors: list[str] = []
    if "python scripts/render_ticket_desk.py" in body:
        errors.append("renderer commands must use a skill-relative path")
    if "skills/jira-ticket-desk/scripts/render_ticket_desk.py" not in body:
        errors.append("renderer commands missing repo-local skill path")
    rules_path = skill_dir / "references" / "ticket-desk-rules.md"
    if rules_path.exists():
        rules = rules_path.read_text(encoding="utf-8")
        if "Unknown bucket names are normalized to `next`" not in rules:
            errors.append("rules reference missing unknown bucket fallback contract")
    return errors


def validate_release_automation(frontmatter: dict[str, Any], body: str) -> list[str]:
    errors: list[str] = []
    description = str(frontmatter.get("description", ""))
    for required in (
        "gradle/libs.versions.toml",
        "versionCode",
        ".github/workflows/app_deploy.yml",
    ):
        if required not in description:
            errors.append(f"frontmatter missing release repo constraint: {required}")
    if "This is a docs-only skill" in body:
        errors.append("body says docs-only while execute mode mutates external state")
    if "Default to `dry-run`" not in body:
        errors.append("body must state dry-run is the default release mode")
    return errors


def validate_skill_quality_contracts(
    name: str, skill_dir: Path, frontmatter: dict[str, Any], body: str
) -> list[str]:
    if name == "agent-instructions-improver":
        return validate_agent_instructions_improver(skill_dir, frontmatter, body)
    if name == "codebase-codemap":
        return validate_codebase_codemap(skill_dir, frontmatter, body)
    if name == "html-report-generator":
        return validate_html_report_generator(skill_dir, body)
    if name == "jira-ticket-desk":
        return validate_jira_ticket_desk(skill_dir, body)
    if name == "release-automation":
        return validate_release_automation(frontmatter, body)
    return []


def validate_skill(
    skill_dir: Path, readme_names: set[str], *, require_codex_meta: bool
) -> list[str]:
    name = skill_dir.name
    errors: list[str] = []
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.exists():
        return ["missing SKILL.md"]
    try:
        frontmatter, body = split_frontmatter(skill_path.read_text(encoding="utf-8"), skill_path)
    except Exception as exc:  # noqa: BLE001
        return [f"frontmatter parse error: {exc}"]
    fm_name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not isinstance(fm_name, str) or not fm_name.strip():
        errors.append("frontmatter missing name")
    elif fm_name != name:
        errors.append(f"frontmatter name {fm_name!r} != folder")
    if not isinstance(description, str) or not description.strip():
        errors.append("frontmatter missing description")
    body_lines = len([line for line in body.splitlines() if line.strip()])
    if body_lines < 3:
        errors.append(f"SKILL.md body too short ({body_lines} lines)")
    if name not in readme_names:
        errors.append("not listed in README")
    meta_path = skill_dir / "agents" / "openai.yaml"
    if require_codex_meta and not meta_path.exists():
        errors.append("missing agents/openai.yaml")
    errors.extend(validate_codex_meta(skill_dir))
    errors.extend(validate_skill_quality_contracts(name, skill_dir, frontmatter, body))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-codex-meta", action="store_true")
    args = parser.parse_args(argv)

    readme_names = readme_skill_names()
    fail = False
    count = 0
    for skill_dir in sorted(path for path in SKILLS_DIR.iterdir() if path.is_dir()):
        count += 1
        errors = validate_skill(
            skill_dir,
            readme_names,
            require_codex_meta=args.require_codex_meta,
        )
        parity = (
            "codex+claude" if (skill_dir / "agents" / "openai.yaml").exists() else "claude-only"
        )
        if errors:
            fail = True
            for error in errors:
                print(f"[fail] {skill_dir.name}: {error}")
        else:
            print(f"[ok] {skill_dir.name} ({parity})")
    print(f"[verify-skills] checked {count} skills")
    if fail:
        print("[verify-skills] FAIL")
        return 1
    print("[verify-skills] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
