---
name: agent-instructions-improver
description: Audit and improve AGENTS.md and related agent instruction files across repositories. Use when the user asks to check, audit, update, improve, migrate, or consolidate AGENTS.md, CLAUDE.md, GEMINI.md, Copilot instructions, Cursor rules, or project operating guides for shared AI-agent context. Reports quality findings before proposing targeted updates.
---

# Agent Instructions Improver

Audit, evaluate, and improve repository instruction files so Codex, Claude Code, Gemini, Copilot, Cursor, and other agent platforms can share clear project context.

**Default source of truth:** prefer repo-local `AGENTS.md` for shared project instructions. Keep platform-specific files only for platform-only behavior, compatibility pointers, or local/private overrides.

**This skill can write to agent instruction files.** After presenting a quality report and getting user approval, it updates files with targeted improvements.

## Workflow

### Phase 1: Discovery

Find shared and platform-specific agent instruction files in the repository:

```bash
find . \( \
  -name "AGENTS.md" -o \
  -name "CLAUDE.md" -o \
  -name ".claude.md" -o \
  -name ".claude.local.md" -o \
  -name "GEMINI.md" -o \
  -path "*/.github/copilot-instructions.md" -o \
  -path "*/.cursor/rules/*" \
\) 2>/dev/null | head -80
```

**File Types & Locations:**

| Type | Location | Purpose |
|------|----------|---------|
| Shared root guide | `./AGENTS.md` | Primary project context, checked into git and shared across agent platforms |
| Platform compatibility | `./CLAUDE.md`, `./GEMINI.md`, `.github/copilot-instructions.md`, `.cursor/rules/*` | Platform-specific entry points or small pointers to the shared guide |
| Local overrides | `./.claude.local.md`, ignored local files | Personal/local settings that should not be shared |
| Package-specific | `./packages/*/AGENTS.md` or nested `AGENTS.md` | Module-level context in monorepos |
| Subdirectory | Any nested location | Feature/domain-specific context |

**Migration note:** If a repo has `CLAUDE.md` but no `AGENTS.md`, recommend making `AGENTS.md` the shared canonical guide and turning `CLAUDE.md` into a small compatibility file or symlink only when that is appropriate for the repo.

### Phase 2: Quality Assessment

For each instruction file, evaluate against quality criteria. See [references/quality-criteria.md](references/quality-criteria.md) for detailed rubrics.

**Quick Assessment Checklist:**

| Criterion | Weight | Check |
|-----------|--------|-------|
| Commands/workflows documented | High | Are build/test/deploy commands present? |
| Architecture clarity | High | Can future agents understand the codebase structure? |
| Non-obvious patterns | Medium | Are gotchas and quirks documented? |
| Conciseness | Medium | No verbose explanations or obvious info? |
| Currency | High | Does it reflect current codebase state? |
| Actionability | High | Are instructions executable, not vague? |
| Cross-platform fit | Medium | Is shared guidance in `AGENTS.md` and platform-specific guidance isolated? |

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
| Commands/workflows | X/20 | ... |
| Architecture clarity | X/20 | ... |
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

2. **Keep it minimal** - Avoid:
   - Restating what's obvious from the code
   - Generic best practices already covered
   - One-off fixes unlikely to recur
   - Verbose explanations when a one-liner suffices

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

## User Tips to Share

When presenting recommendations, remind users:

- **Prefer `AGENTS.md` for shared rules**: Put durable project behavior where multiple agents can read it.
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
