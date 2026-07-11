---
name: agent-instructions-improver
description: Audit AGENTS.md quality, consolidate shared agent instruction files, or apply approved targeted updates to AGENTS.md, CLAUDE.md, GEMINI.md, Copilot instructions, Cursor rules, and project operating guides. Use for durable session-to-instructions capture or explicit agent-instruction quality work, not simple file lookup. Reports quality findings before proposing updates.
capabilities:
  read_only: false
  local_write: true
  network_read: false
  external_write: false
  credentials: false
  hooks: false
---

# Agent Instructions Improver

Audit, evaluate, and improve repository instruction files so Codex, Claude Code, Gemini, Copilot, Cursor, and other agent platforms can share clear project context.

**Default source of truth:** prefer repo-local `AGENTS.md` for shared project instructions. Keep platform-specific files only for platform-only behavior, compatibility pointers, or local/private overrides.

**Session-to-AGENTS.md rule:** only promote durable, reusable project knowledge from a session. Do not add raw transcripts, one-off task status, secrets, private local state, or facts that belong in code, tests, docs, or commit messages.

**This skill can write to agent instruction files.** After presenting a quality report and getting user approval, it updates files with targeted improvements.

## Workflow

### Plugin Skill Review Mode

When the task is to review or promote this skill rather than audit a target repository, answer the specific maintenance question directly. Name `agent-instructions-improver`, `SKILL.md`, relevant validation commands/checks, and any bundled `references/`, `scripts/`, or `assets/` that must be carried forward during promotion.

### Session Learning Capture Mode

When the user asks to convert a session, transcript, handoff, review, or recent debugging run into `AGENTS.md` / agentmd updates, use this workflow before editing:

1. **Extract candidate learnings** - Look for reusable commands, verification paths, repo boundaries, ownership rules, tool constraints, recurring gotchas, and external-state caveats.
2. **Reject non-durable material** - Exclude one-off progress notes, raw session logs, secrets, personal data, temporary blockers without a reusable rule, and implementation details already captured in code or tests.
3. **Route each learning** - Put shared project behavior in `AGENTS.md`; keep platform-only behavior in `CLAUDE.md`, `GEMINI.md`, Copilot, or Cursor files; route local/private preferences to ignored local files or user-level memory instead.
4. **Report before patching** - Show accepted learnings, rejected learnings, target file(s), and a concise proposed diff. If no durable learning survives, say no update is recommended.
5. **Apply narrowly** - Preserve the target file's structure, add the smallest useful text, and verify with `git diff --check` scoped to the touched instruction files when possible.

### Phase 1: Discovery

Find shared and platform-specific agent instruction files in the repository:

```bash
agent_instruction_files="$(mktemp)"
find . \( \
  -name "AGENTS.md" -o \
  -name "AGENT.md" -o \
  -name "CLAUDE.md" -o \
  -name ".claude.md" -o \
  -name ".claude.local.md" -o \
  -name "GEMINI.md" -o \
  -path "*/.github/copilot-instructions.md" -o \
  -path "*/.cursor/rules/*" \
\) 2>/dev/null | sort > "$agent_instruction_files"
wc -l "$agent_instruction_files"
sed -n '1,80p' "$agent_instruction_files"
```

If the count is greater than 80, treat the printed list as a preview only. Narrow
the scope or inspect the saved file before reporting coverage.

**File Types & Locations:**

| Type | Location | Purpose |
|------|----------|---------|
| Shared root guide | `./AGENTS.md` | Primary project context, checked into git and shared across agent platforms |
| Legacy/shared alias | `./AGENT.md` | Treat as a possible older/shared guide; prefer consolidating to `AGENTS.md` when safe |
| Platform compatibility | `./CLAUDE.md`, `./GEMINI.md`, `.github/copilot-instructions.md`, `.cursor/rules/*` | Platform-specific entry points or small pointers to the shared guide |
| Local overrides | `./.claude.local.md`, ignored local files | Personal/local settings that should not be shared |
| Package-specific | `./packages/*/AGENTS.md` or nested `AGENTS.md` | Module-level context in monorepos |
| Subdirectory | Any nested location | Feature/domain-specific context |

**Migration note:** If a repo has `CLAUDE.md` but no `AGENTS.md`, recommend making `AGENTS.md` the shared canonical guide and turning `CLAUDE.md` into a small compatibility file or symlink only when that is appropriate for the repo.

### Phase 2: Quality Assessment

For each instruction file, evaluate against quality criteria. See [references/quality-criteria.md](references/quality-criteria.md) for detailed rubrics.

**Quick Assessment Checklist:**

The numeric quality score is always out of 100 points:

| Criterion | Weight | Check |
|-----------|--------|-------|
| Commands/workflows documented | 15 points | Are build/test/deploy commands present? |
| Architecture clarity | 15 points | Can future agents understand the codebase structure? |
| Non-obvious patterns | 15 points | Are gotchas and quirks documented? |
| Conciseness | 15 points | No verbose explanations or obvious info? |
| Currency | 15 points | Does it reflect current codebase state? |
| Actionability | 15 points | Are instructions executable, not vague? |
| Cross-platform fit | 10 points | Is shared guidance in `AGENTS.md` and platform-specific guidance isolated? |

When the review is sourced from a session, also apply the session durability
check. Penalize the relevant criterion above instead of adding extra points.

**Quality Scores:**
- **A (90-100)**: Comprehensive, current, actionable
- **B (70-89)**: Good coverage, minor gaps
- **C (50-69)**: Basic info, missing key sections
- **D (30-49)**: Sparse or outdated
- **F (0-29)**: Missing or severely outdated

### Phase 3: Quality Report Output

**ALWAYS output the quality report BEFORE making any updates.**

Format:

```
## Agent Instructions Quality Report

### Summary
- Files found: X
- Average score: X/100
- Files needing update: X
- Recommended source of truth: AGENTS.md / existing platform file / none yet

### File-by-File Assessment

#### 1. ./AGENTS.md (Shared Root Guide)
**Score: XX/100 (Grade: X)**

| Criterion | Score | Notes |
|-----------|-------|-------|
| Commands/workflows | X/15 | ... |
| Architecture clarity | X/15 | ... |
| Non-obvious patterns | X/15 | ... |
| Conciseness | X/15 | ... |
| Currency | X/15 | ... |
| Actionability | X/15 | ... |
| Cross-platform fit | X/10 | ... |

**Issues:**
- [List specific problems]

**Recommended additions:**
- [List what should be added]

#### 2. ./CLAUDE.md (Platform Compatibility)
...
```

### Phase 4: Targeted Updates

After outputting the quality report, ask user for confirmation before updating.

**Update Guidelines (Critical):**

1. **Propose targeted additions only** - Focus on genuinely useful info:
   - Commands or workflows discovered during analysis
   - Gotchas or non-obvious patterns found in code
   - Package relationships that weren't clear
   - Testing approaches that work
   - Configuration quirks
   - Session learnings that are likely to recur in future agent work

2. **Keep it minimal** - Avoid:
   - Restating what's obvious from the code
   - Generic best practices already covered
   - One-off fixes unlikely to recur
   - Verbose explanations when a one-liner suffices
   - Status updates, raw transcripts, or task-specific breadcrumbs

3. **Show diffs** - For each change, show:
   - Which instruction file to update
   - The specific addition (as a diff or quoted block)
   - Brief explanation of why this helps future sessions

**Diff Format:**

```markdown
### Update: ./AGENTS.md

**Why:** Build command was missing, causing confusion about how to run the project.

```diff
+ ## Quick Start
+
+ ```bash
+ npm install
+ npm run dev  # Start development server on port 3000
+ ```
```
```

### Phase 5: Apply Updates

After user approval, apply changes using the Edit tool. Preserve existing content structure.

## Templates

See [references/templates.md](references/templates.md) for `AGENTS.md` templates by project type and compatibility patterns for platform-specific files.

## Common Issues to Flag

1. **Stale commands**: Build commands that no longer work
2. **Missing dependencies**: Required tools not mentioned
3. **Outdated architecture**: File structure that's changed
4. **Missing environment setup**: Required env vars or config
5. **Broken test commands**: Test scripts that have changed
6. **Undocumented gotchas**: Non-obvious patterns not captured
7. **Session residue**: One-off status or transcript details added as if they were durable project rules

## User Tips to Share

When presenting recommendations, remind users:

- **Prefer `AGENTS.md` for shared rules**: Put durable project behavior where multiple agents can read it.
- **Session learnings need a filter**: Capture reusable rules, not a diary of what happened.
- **Keep it concise**: Agent instruction files should be human-readable; dense is better than verbose
- **Actionable commands**: All documented commands should be copy-paste ready
- **Use local overrides sparingly**: Personal preferences belong in ignored local files or user-level settings, not shared project guides
- **Avoid duplicate guides**: If `CLAUDE.md`, `GEMINI.md`, or Copilot/Cursor files repeat `AGENTS.md`, consolidate them into short pointers

## What Makes a Great Agent Instruction File

**Key principles:**
- Concise and human-readable
- Actionable commands that can be copy-pasted
- Project-specific patterns, not generic advice
- Non-obvious gotchas and warnings
- Shared defaults live in `AGENTS.md`; platform quirks stay in platform files

**Recommended sections** (use only what's relevant):
- Commands (build, test, dev, lint)
- Architecture (directory structure)
- Key Files (entry points, config)
- Code Style (project conventions)
- Environment (required vars, setup)
- Testing (commands, patterns)
- Gotchas (quirks, common mistakes)
- Workflow (when to do what)
