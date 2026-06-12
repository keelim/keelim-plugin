# Agent Instructions Improver

Audit repository agent instruction files and produce a quality report before any
update is proposed.

Use `AGENTS.md` as the preferred shared source of truth. Treat `CLAUDE.md`,
`GEMINI.md`, Copilot instructions, Cursor rules, and local overrides as
platform-specific entry points unless repository evidence says otherwise.

Evaluate instruction files for actionable commands, architecture clarity,
non-obvious project patterns, conciseness, currency, cross-platform fit, and
whether the guidance is grounded in the current repository.

When recommending changes:

- Keep additions targeted to commands, workflows, gotchas, package boundaries,
  test procedures, environment setup, or other durable repo-specific facts.
- Avoid generic advice, repeated guidance, stale assumptions, and unverified
  claims about tools or architecture.
- Preserve local/private overrides and avoid changing unrelated repositories.
- Show the quality report first, then propose exact diffs or short additions.
- Prefer small reversible edits that make future agent sessions safer.

A good response is evidence-backed, concise, and explicit about uncertainty.
