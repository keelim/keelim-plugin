# Agent Instruction File Quality Criteria

## Scoring Rubric

### 1. Commands/Workflows (15 points)

**15 points**: All essential commands documented with context
- Build, test, lint, deploy commands present
- Development workflow clear
- Common operations documented

**11 points**: Most commands present, some missing context

**8 points**: Basic commands only, no workflow

**4 points**: Few commands, many missing

**0 points**: No commands documented

### 2. Architecture Clarity (15 points)

**15 points**: Clear codebase map
- Key directories explained
- Module relationships documented
- Entry points identified
- Data flow described where relevant

**11 points**: Good structure overview, minor gaps

**8 points**: Basic directory listing only

**4 points**: Vague or incomplete

**0 points**: No architecture info

### 3. Non-Obvious Patterns (15 points)

**15 points**: Gotchas and quirks captured
- Known issues documented
- Workarounds explained
- Edge cases noted
- "Why we do it this way" for unusual patterns

**10 points**: Some patterns documented

**5 points**: Minimal pattern documentation

**0 points**: No patterns or gotchas

### 4. Conciseness (15 points)

**15 points**: Dense, valuable content
- No filler or obvious info
- Each line adds value
- No redundancy with code comments

**10 points**: Mostly concise, some padding

**5 points**: Verbose in places

**0 points**: Mostly filler or restates obvious code

### 5. Currency (15 points)

**15 points**: Reflects current codebase
- Commands work as documented
- File references accurate
- Tech stack current

**10 points**: Mostly current, minor staleness

**5 points**: Several outdated references

**0 points**: Severely outdated

### 6. Actionability (15 points)

**15 points**: Instructions are executable
- Commands can be copy-pasted
- Steps are concrete
- Paths are real

**10 points**: Mostly actionable

**5 points**: Some vague instructions

**0 points**: Vague or theoretical

### 7. Cross-Platform Fit (10 points)

**10 points**: Shared rules are centralized in `AGENTS.md`, with platform-specific files kept minimal

**7 points**: Mostly centralized, with minor duplication across platform files

**4 points**: Useful guidance exists, but ownership between `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, Copilot, or Cursor files is unclear

**0 points**: Multiple instruction files conflict or duplicate large sections

## Session-to-AGENTS.md Durability Check

When an update is sourced from a session, transcript, handoff, or recent debugging run, filter each candidate learning before scoring the target file:

| Keep | Reject |
|------|--------|
| Reusable commands or validation paths | Raw transcript excerpts |
| Repo boundaries and ownership rules | One-off task status |
| Recurrent gotchas and workarounds | Secrets, private data, or local-only state |
| Tool constraints future agents must know | Temporary blockers without a general rule |
| External-state caveats that change workflow | Details already captured better in code, tests, docs, or commits |

Treat session residue as a conciseness and currency problem. A good `AGENTS.md` teaches future sessions how to work; it does not archive what happened in the last one.

## Assessment Process

1. Read the instruction file completely
2. Cross-reference with actual codebase:
   - Run documented commands when feasible
   - For commands not run, record `not run` plus the reason
   - Check if referenced files exist
   - Verify architecture descriptions
3. Score each criterion
4. Calculate total and assign grade
5. List specific issues found
6. Propose concrete improvements

## Red Flags

- Commands that would fail (wrong paths, missing deps)
- References to deleted files/folders
- Outdated tech versions
- Copy-paste from templates without customization
- Generic advice not specific to the project
- "TODO" items never completed
- Duplicate or conflicting info across `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, Copilot, or Cursor instruction files
