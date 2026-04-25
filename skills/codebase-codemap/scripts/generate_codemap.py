#!/usr/bin/env python3
"""Generate a compact, source-led codemap for agent onboarding."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None


EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".omx",
    ".next",
    ".nuxt",
    ".turbo",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "bower_components",
    "dist",
    "build",
    "coverage",
    "target",
    "out",
    ".gradle",
    ".idea",
    ".vscode",
    "DerivedData",
    "Pods",
}

EXCLUDED_FILES = {
    ".git",
    ".DS_Store",
}

ALLOWED_HIDDEN_DIRS = {".github", ".codex", ".claude"}

BINARY_EXTENSIONS = {
    ".7z",
    ".a",
    ".bin",
    ".bmp",
    ".class",
    ".db",
    ".dmg",
    ".docx",
    ".DS_Store",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".mov",
    ".mp4",
    ".o",
    ".otf",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".tar",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}

LANGUAGE_BY_EXTENSION = {
    ".c": "C",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".go": "Go",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".md": "Markdown",
    ".mjs": "JavaScript",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".sh": "Shell",
    ".sql": "SQL",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
    ".yaml": "YAML",
    ".yml": "YAML",
}

MANIFEST_NAMES = {
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "Makefile",
    "justfile",
    "package.json",
    "bun.lock",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "pom.xml",
    "Gemfile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}

ENTRYPOINT_NAMES = {
    "app.py",
    "main.py",
    "server.py",
    "manage.py",
    "index.js",
    "index.jsx",
    "index.ts",
    "index.tsx",
    "main.js",
    "main.jsx",
    "main.ts",
    "main.tsx",
    "App.jsx",
    "App.tsx",
    "page.tsx",
    "page.jsx",
    "route.ts",
    "route.js",
    "layout.tsx",
    "cli.py",
}

TEST_RE = re.compile(r"(^|/)(test|tests|spec|__tests__)(/|$)|(_test|\.test|\.spec)\.")

SYMBOL_PATTERNS = {
    ".py": re.compile(r"^(?:async\s+)?def\s+([A-Za-z_][\w]*)\s*\(|^class\s+([A-Za-z_][\w]*)\b"),
    ".js": re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|"
        r"^(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b|"
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*="
    ),
    ".jsx": re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|"
        r"^(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b|"
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*="
    ),
    ".ts": re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|"
        r"^(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b|"
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*="
    ),
    ".tsx": re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|"
        r"^(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b|"
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*="
    ),
    ".go": re.compile(r"^func\s+(?:\([^)]+\)\s*)?([A-Za-z_][\w]*)\s*\("),
    ".rs": re.compile(r"^(?:pub\s+)?(?:async\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z_][\w]*)\b"),
    ".kt": re.compile(r"^(?:class|object|interface|fun)\s+([A-Za-z_][\w]*)\b"),
    ".java": re.compile(r"^(?:public|private|protected|final|abstract|static|\s)+\s*(?:class|interface|enum)\s+([A-Za-z_][\w]*)\b"),
    ".swift": re.compile(r"^(?:public\s+|private\s+)?(?:func|class|struct|enum|protocol)\s+([A-Za-z_][\w]*)\b"),
    ".rb": re.compile(r"^def\s+([A-Za-z_][\w!?=]*)\b|^class\s+([A-Za-z_:][\w:]*)\b|^module\s+([A-Za-z_:][\w:]*)\b"),
}


def relpath(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def should_skip_dir(path: Path) -> bool:
    name = path.name
    if name in EXCLUDED_DIRS:
        return True
    return name.startswith(".") and name not in ALLOWED_HIDDEN_DIRS


def is_probably_binary(path: Path) -> bool:
    if path.suffix in BINARY_EXTENSIONS or path.name in BINARY_EXTENSIONS:
        return True
    try:
        chunk = path.read_bytes()[:1024]
    except OSError:
        return True
    return b"\0" in chunk


def iter_repo_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        dirnames[:] = sorted(
            dirname for dirname in dirnames if not should_skip_dir(current_path / dirname)
        )
        for filename in sorted(filenames):
            path = current_path / filename
            if path.name in EXCLUDED_FILES:
                continue
            if path.is_file() and not is_probably_binary(path):
                files.append(path)
    return files


def read_text(path: Path, max_bytes: int = 200_000) -> str:
    try:
        data = path.read_bytes()[:max_bytes]
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def project_filename(root: Path, override: str | None) -> str:
    raw_name = override or root.name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name).strip(".-")
    return f"{cleaned or 'project'}.md"


def classify_repo(files: list[Path], root: Path) -> list[str]:
    names = {relpath(path, root) for path in files}
    labels: list[str] = []
    checks = [
        ("Node/JavaScript", "package.json" in names),
        ("Python", "pyproject.toml" in names or "requirements.txt" in names),
        ("Rust", "Cargo.toml" in names),
        ("Go", "go.mod" in names),
        ("Java/Kotlin/Gradle", any(name.endswith(("build.gradle", "build.gradle.kts")) for name in names)),
        ("Maven", "pom.xml" in names),
        ("Ruby", "Gemfile" in names),
        ("Docker", any(Path(name).name in {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"} for name in names)),
    ]
    for label, present in checks:
        if present:
            labels.append(label)
    return labels or ["Source repository"]


def collect_manifests(files: list[Path], root: Path) -> list[str]:
    result = []
    for path in files:
        rel = relpath(path, root)
        if path.name in MANIFEST_NAMES or rel.startswith(".github/workflows/"):
            result.append(rel)
    return sorted(result)


def collect_entrypoints(files: list[Path], root: Path) -> list[str]:
    result = []
    for path in files:
        rel = relpath(path, root)
        parts = set(path.parts)
        if path.name in ENTRYPOINT_NAMES:
            result.append(rel)
        elif "/cmd/" in f"/{rel}/" and path.name == "main.go":
            result.append(rel)
        elif "api" in parts and path.suffix in {".py", ".js", ".ts", ".tsx", ".go"}:
            result.append(rel)
        elif rel.startswith(("app/", "pages/", "routes/", "src/routes/")) and path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
            result.append(rel)
    return sorted(dict.fromkeys(result))


def collect_tests(files: list[Path], root: Path) -> list[str]:
    tests = [relpath(path, root) for path in files if TEST_RE.search(relpath(path, root))]
    return sorted(tests)


def collect_language_counts(files: list[Path]) -> collections.Counter[str]:
    counts: collections.Counter[str] = collections.Counter()
    for path in files:
        language = LANGUAGE_BY_EXTENSION.get(path.suffix)
        if language:
            counts[language] += 1
        else:
            counts[path.suffix or "[no extension]"] += 1
    return counts


def collect_directory_summary(files: list[Path], root: Path, max_items: int) -> list[tuple[str, int, list[str]]]:
    grouped: dict[str, list[str]] = collections.defaultdict(list)
    for path in files:
        rel = relpath(path, root)
        parts = rel.split("/")
        key = parts[0] if len(parts) > 1 else "."
        grouped[key].append(rel)
    rows = []
    for key, paths in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        rows.append((key, len(paths), sorted(paths)[:3]))
    return rows[:max_items]


def collect_symbols(
    files: list[Path], root: Path, max_symbol_files: int, max_symbols_per_file: int
) -> list[tuple[str, list[str]]]:
    symbol_files: list[tuple[str, list[str]]] = []
    for path in files:
        pattern = SYMBOL_PATTERNS.get(path.suffix)
        if not pattern:
            continue
        if len(symbol_files) >= max_symbol_files:
            break
        symbols: list[str] = []
        for line_number, line in enumerate(read_text(path).splitlines(), start=1):
            stripped = line.strip()
            match = pattern.search(stripped)
            if not match:
                continue
            name = next((group for group in match.groups() if group), None)
            if name:
                symbols.append(f"{name} (L{line_number})")
            if len(symbols) >= max_symbols_per_file:
                break
        if symbols:
            symbol_files.append((relpath(path, root), symbols))
    return symbol_files


def read_package_scripts(root: Path) -> list[str]:
    package_json = root / "package.json"
    if not package_json.exists():
        return []
    try:
        package = json.loads(read_text(package_json))
    except json.JSONDecodeError:
        return ["package.json scripts could not be parsed"]
    scripts = package.get("scripts", {})
    if not isinstance(scripts, dict):
        return []
    return [f"npm script `{name}`: {command}" for name, command in sorted(scripts.items())]


def read_pyproject_scripts(root: Path) -> list[str]:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists() or tomllib is None:
        return []
    try:
        parsed = tomllib.loads(read_text(pyproject))
    except Exception:
        return ["pyproject.toml could not be parsed"]
    scripts = parsed.get("project", {}).get("scripts", {})
    if not isinstance(scripts, dict):
        return []
    return [f"Python script `{name}`: {target}" for name, target in sorted(scripts.items())]


def select_read_first(files: list[Path], root: Path, manifests: list[str], entrypoints: list[str]) -> list[str]:
    candidates: list[str] = []
    priority_names = ["AGENTS.md", "README.md", "CLAUDE.md"]
    for name in priority_names:
        if (root / name).exists():
            candidates.append(name)
    candidates.extend(path for path in manifests if path.startswith("docs/CODEMAPS/"))
    candidates.extend(path for path in manifests if path not in candidates and Path(path).name in {"package.json", "pyproject.toml", "Cargo.toml", "go.mod"})
    candidates.extend(path for path in entrypoints if path not in candidates)
    candidates.extend(relpath(path, root) for path in files if relpath(path, root).endswith("/AGENTS.md"))
    return list(dict.fromkeys(candidates))[:16]


def markdown_list(items: list[str], empty: str, limit: int | None = None) -> str:
    if not items:
        return f"- {empty}\n"
    visible = items if limit is None else items[:limit]
    output = "".join(f"- `{item}`\n" for item in visible)
    if limit is not None and len(items) > limit:
        output += f"- ... {len(items) - limit} more\n"
    return output


def generate_markdown(args: argparse.Namespace) -> str:
    root = Path(args.repo).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Repository path is not a directory: {root}")

    files = iter_repo_files(root)
    manifests = collect_manifests(files, root)
    entrypoints = collect_entrypoints(files, root)
    tests = collect_tests(files, root)
    language_counts = collect_language_counts(files)
    directories = collect_directory_summary(files, root, args.max_dirs)
    symbols = collect_symbols(files, root, args.max_symbol_files, args.max_symbols_per_file)
    package_scripts = read_package_scripts(root)
    pyproject_scripts = read_pyproject_scripts(root)
    read_first = select_read_first(files, root, manifests, entrypoints)
    repo_shape = classify_repo(files, root)

    generated_at = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# Agent Codemap",
        "",
        f"- Repository: `{root.name}`",
        f"- Root: `{root}`",
        f"- Generated: {generated_at}",
        f"- Files scanned: {len(files)}",
        f"- Detected shape: {', '.join(repo_shape)}",
        "",
        "## Read First",
        markdown_list(read_first, "No obvious read-first files detected. Start with manifests and top-level directories.").rstrip(),
        "",
        "## Repository Shape",
    ]

    for language, count in language_counts.most_common(12):
        lines.append(f"- {language}: {count} files")

    lines.extend(["", "## Entrypoints", markdown_list(entrypoints, "No obvious entrypoint files detected.", args.max_files).rstrip()])

    lines.extend(["", "## Key Directories"])
    if directories:
        for directory, count, examples in directories:
            sample = ", ".join(f"`{example}`" for example in examples)
            lines.append(f"- `{directory}/`: {count} files; examples: {sample}")
    else:
        lines.append("- No source files detected.")

    lines.extend(["", "## Dependencies and Tooling", markdown_list(manifests, "No common manifests detected.", args.max_files).rstrip()])

    commands = package_scripts + pyproject_scripts
    lines.extend(["", "## Useful Commands"])
    if commands:
        for command in commands[: args.max_commands]:
            lines.append(f"- {command}")
        if len(commands) > args.max_commands:
            lines.append(f"- ... {len(commands) - args.max_commands} more")
    else:
        lines.append("- No package or pyproject scripts detected. Inspect README or project docs for commands.")

    lines.extend(["", "## Tests and Verification", markdown_list(tests, "No obvious test files detected.", args.max_files).rstrip()])

    lines.extend(["", "## Symbol Landmarks"])
    if symbols:
        for path, names in symbols[: args.max_symbol_files]:
            joined = ", ".join(names)
            lines.append(f"- `{path}`: {joined}")
    else:
        lines.append("- No symbols extracted from supported languages.")

    lines.extend(["", "## Open Questions"])
    if not tests:
        lines.append("- Verification surface is unclear; inspect README, CI, or manifests before changing behavior.")
    if not any(path.startswith("docs/CODEMAPS/") for path in manifests):
        lines.append("- No existing `docs/CODEMAPS/*` files were found.")
    if "AGENTS.md" not in manifests:
        lines.append("- No root `AGENTS.md` was found; check for deeper instruction files before editing.")
    if not entrypoints:
        lines.append("- Entrypoints were not obvious from file names; inspect manifests and top-level directories.")
    if tests and any(path.startswith("docs/CODEMAPS/") for path in manifests):
        lines.append("- No immediate structural gaps detected by the generator; verify claims against source before editing.")

    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="Repository root to scan")
    parser.add_argument("--output", help="Exact Markdown output path, relative to the repo unless absolute")
    parser.add_argument(
        "--output-dir",
        help="Directory for project-named output, relative to the repo unless absolute",
    )
    parser.add_argument(
        "--project-name",
        help="Override the project name used for the default output filename",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the codemap; with no output options, this skips the default file write",
    )
    parser.add_argument("--max-files", type=int, default=80, help="Maximum files to list in large sections")
    parser.add_argument("--max-dirs", type=int, default=24, help="Maximum directories to summarize")
    parser.add_argument("--max-commands", type=int, default=30, help="Maximum commands to list")
    parser.add_argument("--max-symbol-files", type=int, default=80, help="Maximum files with symbol landmarks")
    parser.add_argument("--max-symbols-per-file", type=int, default=8, help="Maximum symbols per file")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    markdown = generate_markdown(args)
    root = Path(args.repo).resolve()
    output: Path | None = None
    if args.output:
        output = Path(args.output)
    elif args.output_dir:
        output = Path(args.output_dir) / project_filename(root, args.project_name)
    elif not args.stdout:
        output = Path("docs/CODEMAPS") / project_filename(root, args.project_name)

    if output is not None:
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
        print(f"Wrote {output}")

    if args.stdout or output is None:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
