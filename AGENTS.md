# keelim-plugin working guide

The maintained source for reusable local Codex and Claude skills. Each workflow keeps its own capabilities and safety contract; repository tooling validates catalogs and reviews promotion candidates.

## Project structure

```text
./
├── AGENTS.md → Working guide
├── CLAUDE.md → Same guide for Claude
├── docs/
│   ├── architecture.md → Components and data flow
│   ├── business-rules.md → Domain meaning and edge cases
│   ├── security.md → Access, credentials, and protected data
│   ├── standards.md → Change and verification rules
│   ├── engineering-notes.md → Operational traps
│   ├── operations.md → Setup and scoped commands
│   ├── contracts.md → Consumer inputs, outputs, and failures
│   └── tracking/
│       ├── status.md → Capabilities and verified scope
│       ├── findings.md → Unresolved issues
│       └── decisions/
│           ├── index.md → Decision index
│           ├── 0001-single-source-skills.md → One source with explicit installed copies
│           └── 0002-review-before-promotion.md → Compare candidates before applying
├── skills/
│   └── AGENTS.md → Reusable workflow sources
├── scripts/
│   └── AGENTS.md → Catalog and promotion tooling
└── evals/
    └── AGENTS.md → Evaluation fixtures
```

## Hard gates

1. Preserve each skill’s declared effects and workflow-specific safety gates.
2. Review requests inspect evidence without executing the production workflow.
3. Keep one maintained source per skill and regenerate catalogs from it.
4. Keep secrets, session traces, and optimization output outside durable skill sources.

## Before work

Read `docs/standards.md`, `docs/engineering-notes.md`, and the closest module guide.

Before a skill edit read its `SKILL.md` and only the references used by the changed step. Before promotion inspect `scripts/promote_plugin_skills.py` and the candidate diff; use `pyproject.toml` and `scripts/check.sh` for the current verification contract. Before installation inspect whether the destination is a link or a copy.

## Problem routing

Immediately report secret/session-data exposure, unauthorized hook installation or external writes, and a promotion that removed a safety gate. Record other unresolved issues in `docs/tracking/findings.md` with the skill and failing check.
