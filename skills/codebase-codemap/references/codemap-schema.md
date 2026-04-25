# Codemap Schema

Use this reference when editing the generator output, writing a codemap manually, or changing the output contract.

## Purpose
Create a compact source-led map that helps a future agent answer:
- What should I read first?
- Where are the entrypoints?
- Which files define the main behavior?
- How do I verify changes?
- Which claims still need inspection?

## Required Sections
- `Read First`: governing docs and high-signal files in reading order.
- `Repository Shape`: detected stacks and language/file-count signals.
- `Entrypoints`: app, CLI, route, server, and workflow entry files.
- `Key Directories`: top-level ownership map with examples.
- `Dependencies and Tooling`: manifests, locks, CI, Docker, build files.
- `Useful Commands`: scripts discovered from manifests.
- `Tests and Verification`: obvious test files and test folders.
- `Symbol Landmarks`: shallow symbol index for jump-starting search.
- `Open Questions`: gaps the next agent should resolve from source.

## Writing Rules
- Prefer file paths over prose claims.
- Keep each bullet short enough to scan.
- Mark uncertainty in `Open Questions`, not as hidden assumptions.
- Do not include generated dependency code, build outputs, or local runtime state.
- Do not map sibling repositories unless the user asked for workspace scope.

## Refresh Rules
- Regenerate from live source before using a codemap for planning.
- In multi-project workspaces, keep one project-named file per child repo, such as `docs/CODEMAPS/<project-name>.md`.
- After manual edits, run `git diff --check` on the codemap file if it will be committed.
- If generated output conflicts with `README.md`, `AGENTS.md`, or source files, trust source and update the codemap.
- When the generator is too shallow, use its output as an index and add only evidence-backed human judgment.
