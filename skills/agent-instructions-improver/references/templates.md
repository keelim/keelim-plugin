# AGENTS.md Templates

## Key Principles

- **Concise**: Dense, human-readable content; one line per concept when possible
- **Actionable**: Commands should be copy-paste ready
- **Project-specific**: Document patterns unique to this project, not generic advice
- **Current**: All info should reflect actual codebase state

---

## Recommended Sections

Use only the sections relevant to the project. Not all sections are needed.

### Commands

Document the essential commands for working with the project.

```markdown
## Commands

| Command | Description |
|---------|-------------|
| `<install command>` | Install dependencies |
| `<dev command>` | Start development server |
| `<build command>` | Production build |
| `<test command>` | Run tests |
| `<lint command>` | Lint/format code |
```

### Architecture

Describe the project structure so future agents understand where things live.

```markdown
## Architecture

```
<root>/
  <dir>/    # <purpose>
  <dir>/    # <purpose>
  <dir>/    # <purpose>
```
```

### Key Files

List important files that future agents should know about.

```markdown
## Key Files

- `<path>` - <purpose>
- `<path>` - <purpose>
```

### Code Style

Document project-specific coding conventions.

```markdown
## Code Style

- <convention>
- <convention>
- <preference over alternative>
```

### Environment

Document required environment variables and setup.

```markdown
## Environment

Required:
- `<VAR_NAME>` - <purpose>
- `<VAR_NAME>` - <purpose>

Setup:
- <setup step>
```

### Testing

Document testing approach and commands.

```markdown
## Testing

- `<test command>` - <what it tests>
- <testing convention or pattern>
```

### Gotchas

Document non-obvious patterns, quirks, and warnings.

```markdown
## Gotchas

- <non-obvious thing that causes issues>
- <ordering dependency or prerequisite>
- <common mistake to avoid>
```

### Workflow

Document development workflow patterns.

```markdown
## Workflow

- <when to do X>
- <preferred approach for Y>
```

---

## Template: Project Root (Minimal)

```markdown
# <Project Name>

<One-line description>

## Commands

| Command | Description |
|---------|-------------|
| `<command>` | <description> |

## Architecture

```
<structure>
```

## Gotchas

- <gotcha>
```

---

## Template: Project Root (Comprehensive)

```markdown
# <Project Name>

<One-line description>

## Commands

| Command | Description |
|---------|-------------|
| `<command>` | <description> |

## Architecture

```
<structure with descriptions>
```

## Key Files

- `<path>` - <purpose>

## Code Style

- <convention>

## Environment

- `<VAR>` - <purpose>

## Testing

- `<command>` - <scope>

## Gotchas

- <gotcha>
```

---

## Template: Package/Module

For packages within a monorepo or distinct modules.

```markdown
# <Package Name>

<Purpose of this package>

## Usage

```
<import/usage example>
```

## Key Exports

- `<export>` - <purpose>

## Dependencies

- `<dependency>` - <why needed>

## Notes

- <important note>
```

---

## Template: Monorepo Root

```markdown
# <Monorepo Name>

<Description>

## Packages

| Package | Description | Path |
|---------|-------------|------|
| `<name>` | <purpose> | `<path>` |

## Commands

| Command | Description |
|---------|-------------|
| `<command>` | <description> |

## Cross-Package Patterns

- <shared pattern>
- <generation/sync pattern>
```

## Platform Compatibility Files

When a repo needs platform-specific entry points, keep them short and point to the shared guide.

### `CLAUDE.md`

```markdown
# Claude Code Instructions

Use `AGENTS.md` as the shared project operating guide.

Claude-specific notes:
- <only if needed>
```

### `GEMINI.md`

```markdown
# Gemini Instructions

Use `AGENTS.md` as the shared project operating guide.

Gemini-specific notes:
- <only if needed>
```

### `.github/copilot-instructions.md`

```markdown
Follow the project operating guide in `AGENTS.md`.

Copilot-specific notes:
- <only if needed>
```

---

## Template: Session-to-AGENTS.md Report

Use this when turning session learnings into instruction-file updates.

````markdown
## Session-to-AGENTS.md Report

### Durable Candidates

| Learning | Target | Why it belongs |
|----------|--------|----------------|
| <reusable rule or gotcha> | `AGENTS.md` | <future-session value> |

### Rejected

| Item | Reason |
|------|--------|
| <status note or raw detail> | <why it should not enter instructions> |

### Proposed Diff

```diff
+ <smallest useful instruction-file addition>
```
````

If every candidate is rejected, report that no instruction update is recommended.

---

## Update Principles

When updating any agent instruction file:

1. **Be specific**: Use actual file paths, real commands from this project
2. **Be current**: Verify info against the actual codebase
3. **Centralize shared rules**: Put durable project defaults in `AGENTS.md`
4. **Filter session input**: Keep reusable operating knowledge, reject status or transcript residue
5. **Be brief**: One line per concept when possible
6. **Be useful**: Would this help a new agent session understand the project?
