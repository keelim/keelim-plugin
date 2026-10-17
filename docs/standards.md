# Skill maintenance rules

Keep every skill in `skills/<name>/` with `SKILL.md`; front-matter name matches the folder, description states a concrete trigger, and all six capabilities are booleans. Preserve Codex metadata and bundled resources when moving/promoting a skill. Add supporting folders only when the workflow uses them.

Keep user workflow and safety gates in the skill; detailed examples belong in its existing references at the step that uses them. Collection maintenance rules do not belong inside every production workflow. Prefer local sources and user-scope links over duplicate maintained copies.

Additions, removals, and renames update the README Current skills list. After changing a skill folder or that list, run `node scripts/gen-catalog.mjs`, `bash scripts/verify-skills.sh --require-codex-meta`, `node scripts/gen-catalog.mjs --check`, and `git diff --check`, plus affected skill checks. Before promotion use `bash scripts/check.sh`, the CI-equivalent gate.

Keep workflows docs-first unless automation improves repeatability enough to justify maintenance. Do not rewrite a working workflow for a review-only request. Separate metadata/catalog evidence from actual credentials, hooks, rendering, and external execution. Preserve unrelated dirty skill and catalog work, and use the owning source index rather than a parent aggregate.
