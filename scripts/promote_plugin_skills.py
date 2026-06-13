#!/usr/bin/env python3
"""Compare or apply reviewable SKILL.md candidates across keelim-plugin."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
SKILLOPT_ROOT = REPO_ROOT / ".skillopt"
DEFAULT_CANDIDATE_ROOTS = [
    SKILLOPT_ROOT / "promote-candidates",
    SKILLOPT_ROOT / "outputs",
]
STAGE_ROOT = SKILLOPT_ROOT / "promote-candidates"
POST_APPLY_CHECKS = [
    ["node", "scripts/gen-catalog.mjs"],
    [sys.executable, "scripts/run-tests.py"],
]


@dataclass(frozen=True)
class Skill:
    name: str
    path: Path


@dataclass
class PromotionResult:
    skill: str
    current: str
    candidate: str | None
    status: str
    diff_lines: int = 0
    error: str = ""

    def as_json(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "current": self.current,
            "candidate": self.candidate,
            "status": self.status,
            "diff_lines": self.diff_lines,
            "error": self.error,
        }


def skill_dirs() -> list[Skill]:
    if not SKILLS_DIR.exists():
        raise SystemExit(f"skills directory not found: {SKILLS_DIR}")
    skills = []
    for path in sorted(SKILLS_DIR.iterdir()):
        if path.is_dir():
            skill_path = path / "SKILL.md"
            if skill_path.exists():
                skills.append(Skill(name=path.name, path=skill_path))
    return skills


def select_skills(names: list[str]) -> list[Skill]:
    skills = skill_dirs()
    by_name = {skill.name: skill for skill in skills}
    if not names:
        return skills
    missing = [name for name in names if name not in by_name]
    if missing:
        raise SystemExit(f"unknown skill(s): {', '.join(missing)}")
    return [by_name[name] for name in names]


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) == 3:
            return f"---\n{parts[1]}---\n", parts[2]
    return "", text


def frontmatter_values(frontmatter: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip("'\"")
    return values


def preserve_current_frontmatter(current: str, candidate: str) -> str:
    current_frontmatter, _ = split_frontmatter(current)
    _, candidate_body = split_frontmatter(candidate)
    if not current_frontmatter:
        return candidate
    return current_frontmatter + "\n" + candidate_body.lstrip()


def validate_candidate(skill: Skill, text: str) -> str:
    frontmatter, body = split_frontmatter(text)
    values = frontmatter_values(frontmatter)
    if not values.get("name"):
        return "candidate frontmatter missing name"
    if values["name"] != skill.name:
        return f"candidate frontmatter name {values['name']!r} != skill {skill.name!r}"
    if not values.get("description"):
        return "candidate frontmatter missing description"
    body_lines = [line for line in body.splitlines() if line.strip()]
    if len(body_lines) < 3:
        return "candidate body is too short"
    return ""


def candidate_patterns(root: Path, skill_name: str) -> list[str]:
    return [
        f"{skill_name}/SKILL.md",
        f"{skill_name}/best_skill.md",
        f"{skill_name}/**/best_skill.md",
        f"*/{skill_name}/SKILL.md",
        f"*/{skill_name}/best_skill.md",
        f"*/{skill_name}/**/best_skill.md",
    ]


def newest_candidate(skill_name: str, roots: list[Path]) -> Path | None:
    candidates: dict[Path, float] = {}
    for root in roots:
        if not root.exists():
            continue
        for pattern in candidate_patterns(root, skill_name):
            for path in root.glob(pattern):
                if path.is_file():
                    candidates[path.resolve()] = path.stat().st_mtime
    if not candidates:
        return None
    return max(candidates.items(), key=lambda item: item[1])[0]


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def ensure_safe_candidate(candidate_path: Path, roots: list[Path], *, allow_external: bool) -> Path:
    resolved = candidate_path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"candidate is not a file: {candidate_path}")
    if resolved.is_symlink():
        raise SystemExit(f"candidate symlink is not allowed: {candidate_path}")
    if allow_external:
        return resolved
    allowed_roots = [root.expanduser().resolve() for root in roots]
    if not any(is_within(resolved, root) for root in allowed_roots):
        allowed = ", ".join(str(root) for root in allowed_roots)
        raise SystemExit(
            f"candidate must be under an allowed candidate root ({allowed}); "
            "use --allow-external-candidate only after reviewing the source"
        )
    return resolved


def resolve_stage_root(raw_root: str, run_id: str, *, allow_external: bool) -> Path:
    root = Path(raw_root).expanduser() if raw_root else STAGE_ROOT / run_id
    resolved = root.resolve()
    if resolved.exists() and resolved.is_symlink():
        raise SystemExit(f"stage root symlink is not allowed: {root}")
    if not allow_external and not is_within(resolved, STAGE_ROOT):
        raise SystemExit(
            f"stage-current output must stay under {STAGE_ROOT}; "
            "use --allow-external-out-root only for a reviewed local path"
        )
    return resolved


def compare_skill(skill: Skill, candidate_path: Path | None) -> tuple[PromotionResult, str]:
    current = skill.path.read_text(encoding="utf-8")
    if candidate_path is None:
        return (
            PromotionResult(
                skill=skill.name,
                current=str(skill.path),
                candidate=None,
                status="no-candidate",
            ),
            "",
        )
    candidate_raw = candidate_path.read_text(encoding="utf-8")
    candidate = preserve_current_frontmatter(current, candidate_raw)
    error = validate_candidate(skill, candidate)
    if error:
        return (
            PromotionResult(
                skill=skill.name,
                current=str(skill.path),
                candidate=str(candidate_path),
                status="invalid-candidate",
                error=error,
            ),
            "",
        )

    diff = "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            candidate.splitlines(keepends=True),
            fromfile=str(skill.path),
            tofile=str(candidate_path),
        )
    )
    status = "diff" if diff else "no-diff"
    result = PromotionResult(
        skill=skill.name,
        current=str(skill.path),
        candidate=str(candidate_path),
        status=status,
        diff_lines=len(diff.splitlines()) if diff else 0,
    )
    return result, diff


def write_report(path: Path, results: list[PromotionResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "repo": str(REPO_ROOT),
        "results": [result.as_json() for result in results],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def record_apply(skill: Skill, candidate_path: Path, diff: str, content: str) -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    record_dir = SKILLOPT_ROOT / "promoted" / stamp / skill.name
    record_dir.mkdir(parents=True, exist_ok=True)
    (record_dir / "metadata.json").write_text(
        json.dumps(
            {
                "skill": skill.name,
                "current": str(skill.path),
                "candidate": str(candidate_path),
                "applied_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (record_dir / "diff.patch").write_text(diff, encoding="utf-8")
    (record_dir / "SKILL.md").write_text(content, encoding="utf-8")


def run_post_apply_checks() -> int:
    for cmd in POST_APPLY_CHECKS:
        print(f"[promote-skills] verify: {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
        if proc.returncode != 0:
            print(f"[promote-skills] verify failed ({proc.returncode}): {' '.join(cmd)}")
            return proc.returncode
    return 0


def cmd_inventory(args: argparse.Namespace) -> int:
    for skill in select_skills(args.skill):
        print(skill.name)
    return 0


def cmd_stage_current(args: argparse.Namespace) -> int:
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-current")
    root = resolve_stage_root(args.out_root, run_id, allow_external=args.allow_external_out_root)
    for skill in select_skills(args.skill):
        dest = root / skill.name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(skill.path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[stage-current] {skill.name}: {dest}")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    roots = [Path(root) for root in (args.candidate_root or [])] or DEFAULT_CANDIDATE_ROOTS
    skills = select_skills(args.skill)
    explicit_candidate = (
        ensure_safe_candidate(
            Path(args.candidate), roots, allow_external=args.allow_external_candidate
        )
        if args.candidate
        else None
    )
    if explicit_candidate and len(skills) != 1:
        raise SystemExit("--candidate can only be used with exactly one --skill")

    results: list[PromotionResult] = []
    exit_code = 0
    applied_any = False
    for skill in skills:
        candidate_path = explicit_candidate or newest_candidate(skill.name, roots)
        result, diff = compare_skill(skill, candidate_path)
        results.append(result)
        candidate_label = result.candidate or "-"
        print(f"[promote-skills] {skill.name}: {result.status} candidate={candidate_label}")
        if result.error:
            print(f"[promote-skills] {skill.name}: {result.error}")
            exit_code = 1
        if args.require_candidates and result.status == "no-candidate":
            exit_code = 1
        if diff:
            print(diff.rstrip())
        if args.apply and result.status in {"diff", "no-diff"} and candidate_path:
            current = skill.path.read_text(encoding="utf-8")
            content = preserve_current_frontmatter(
                current,
                candidate_path.read_text(encoding="utf-8"),
            )
            skill.path.write_text(content, encoding="utf-8")
            record_apply(skill, candidate_path, diff, content)
            result.status = "applied"
            applied_any = True
            print(f"[promote-skills] {skill.name}: applied -> {skill.path}")

    if args.report:
        write_report(Path(args.report), results)
        print(f"[promote-skills] report={args.report}")
    if not args.apply:
        print("[promote-skills] dry-run: production SKILL.md files not changed")
    if args.apply and applied_any and not args.skip_verify:
        verify_code = run_post_apply_checks()
        if verify_code != 0:
            exit_code = verify_code
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    inventory = sub.add_parser("inventory", help="list current skills")
    inventory.add_argument(
        "--skill", action="append", default=[], help="limit to one skill; repeatable"
    )
    inventory.set_defaults(func=cmd_inventory)

    stage = sub.add_parser(
        "stage-current", help="copy current SKILL.md files into an ignored candidate root"
    )
    stage.add_argument(
        "--skill", action="append", default=[], help="limit to one skill; repeatable"
    )
    stage.add_argument(
        "--run-id", default="", help="candidate run id under .skillopt/promote-candidates"
    )
    stage.add_argument("--out-root", default="", help="explicit candidate root")
    stage.add_argument(
        "--allow-external-out-root",
        action="store_true",
        help="allow stage-current to write outside .skillopt/promote-candidates after local review",
    )
    stage.set_defaults(func=cmd_stage_current)

    promote = sub.add_parser("promote", help="compare or apply skill candidates")
    promote.add_argument(
        "--skill", action="append", default=[], help="limit to one skill; repeatable"
    )
    promote.add_argument("--candidate", default="", help="explicit candidate for a single --skill")
    promote.add_argument(
        "--candidate-root",
        action="append",
        default=[],
        help="root to search for candidates; default: .skillopt/promote-candidates and .skillopt/outputs",
    )
    promote.add_argument(
        "--require-candidates",
        action="store_true",
        help="exit 1 when any selected skill lacks a candidate",
    )
    promote.add_argument("--report", default="", help="write a JSON report")
    promote.add_argument(
        "--apply", action="store_true", help="write candidate content into skills/<name>/SKILL.md"
    )
    promote.add_argument(
        "--skip-verify",
        action="store_true",
        help="skip post-apply catalog and repo validation after a reviewed emergency apply",
    )
    promote.add_argument(
        "--allow-external-candidate",
        action="store_true",
        help="allow an explicit --candidate outside the candidate roots after local review",
    )
    promote.set_defaults(func=cmd_promote)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
