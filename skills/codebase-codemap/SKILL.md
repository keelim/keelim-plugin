---
name: codebase-codemap
description: Generate and refresh concise, source-led codebase maps that help Codex or Claude understand a repository before planning, debugging, reviewing, refactoring, onboarding to unfamiliar code, or making multi-file changes. Use when the user asks for a codemap, code map, repo map, architecture snapshot, source inventory, agent context, or when an agent needs stronger codebase orientation before editing.
---

# Codebase Codemap

## Overview
Use this skill to create an agent-readable map of a repository from live source files. Favor evidence from manifests, entrypoints, tests, docs, and high-signal symbols over speculative prose.

The default output is one compact Markdown file named after the repository folder, such as `docs/CODEMAPS/rich.md` or `docs/CODEMAPS/keelim-plugin.md`. For short-lived work, write a project-named file under `.omx/context/`.

## Workflow
1. Read governing instructions first: nearest `AGENTS.md`, `README.md`, and existing `docs/CODEMAPS/*` if present.
2. If the repository is a superproject, workspace root, or has `.gitmodules`, collect submodule evidence before deciding scope:

```bash
git status --short
git status --ignore-submodules=none --short
git submodule status
git ls-files --stage | rg '160000'
sed -n '1,220p' .gitmodules
```

Use this evidence to distinguish declared `.gitmodules` entries, active gitlinks, initialized submodules, autonomous local repos, and untracked local repos. Do not let a raw source scan blur those boundaries.
3. Run the generator from this skill:

```bash
python3 /path/to/codebase-codemap/scripts/generate_codemap.py /path/to/repo
```

By default this writes `docs/CODEMAPS/<project-name>.md` inside the target repo.

4. Review the generated map before trusting it. Tighten incorrect labels, remove noisy files, and add brief human judgment only where source evidence supports it. In a superproject, treat raw nested-repo scan output as a warning sign: rewrite the root map around root-owned files and submodule/autonomous-repo status, or rerun the generator inside each child repo when that child is explicitly in scope.
5. If the task needs deeper domain context, inspect files named in the generated "Read First", "Entrypoints", and "Symbol Landmarks" sections.
6. For committed codemaps, run a lightweight docs verification such as `git diff --check docs/CODEMAPS/agent-codemap.md`.

## Generator Options
Use the bundled script when a fast first-pass map is enough:

```bash
python3 scripts/generate_codemap.py .
python3 scripts/generate_codemap.py ../rich --output-dir docs/CODEMAPS
python3 scripts/generate_codemap.py . --project-name rich-admin
python3 scripts/generate_codemap.py . --max-files 1200 --max-symbol-files 160
python3 scripts/generate_codemap.py . --stdout
```

In a multi-project workspace, run the script once per child repository. Each run should target the child repo root so the default output lands in that repo as `docs/CODEMAPS/<child-project-name>.md`.

The script uses only Python stdlib. It intentionally ignores common generated/cache directories such as `.git`, `.omx`, `node_modules`, `.next`, `dist`, `build`, `coverage`, `.venv`, and `target`.

## Superprojects and Submodules
When mapping a root workspace that coordinates child Git repositories, the codemap must make repository boundaries explicit. Include a short, evidence-backed summary of:
- `.gitmodules` declarations and tracked branches
- active gitlinks from `git ls-files --stage | rg '160000'`
- `git submodule status` output, including `+`, `-`, or detached/pinned-state signals
- autonomous local repositories that are intentionally not submodules
- untracked local repositories that look like workspace members but are not pinned by the root index

If `.gitmodules` and active gitlinks disagree, record that mismatch in `Open Questions` instead of smoothing it over. If the user explicitly asks to repair, add, or pin submodules, the codemap should provide this evidence as the basis for the follow-up implementation rather than stopping at a generic architecture snapshot.

## Output Standards
Keep the map:
- source-led: cite concrete files and commands
- compact: enough to orient an agent, not a full architecture essay
- current: prefer regenerated evidence over stale hand-written claims
- scoped: describe this repository, not sibling repos, unless the task explicitly asks for workspace-level mapping
- boundary-aware: for superprojects, separate root-owned files, declared submodules, active gitlinks, autonomous repos, and untracked local repos

Include these sections when editing manually:
- `Read First`
- `Repository Shape`
- `Entrypoints`
- `Key Directories`
- `Tests and Verification`
- `Dependencies and Tooling`
- `Symbol Landmarks`
- `Open Questions`

Read `references/codemap-schema.md` before changing the output contract or when manually creating a codemap without the script.

## Good Use
Good request:

```text
Use $codebase-codemap to map this repo before planning the refactor.
```

Good output location:

```text
docs/CODEMAPS/<project-name>.md
```

Use `.omx/context/<task>-codemap.md` instead when the map is task-local or should not be committed.

## Common Mistakes
- Treating the generated map as proof without reading the files it references.
- Writing broad architecture claims that are not grounded in filenames, manifests, or source symbols.
- Including generated directories, dependency vendored code, or local agent runtime state.
- Updating codemaps for sibling repos from a parent workspace unless the user explicitly asked for that scope.
- Treating `.gitmodules` alone as proof that a path is an active submodule; confirm with gitlinks and `git submodule status`.
- Treating a hydrated child repository as root-owned source just because it exists under the workspace directory.
