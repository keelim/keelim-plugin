# Skill collection architecture

`skills/<name>/SKILL.md` is the maintained workflow source. Optional `agents/openai.yaml` supplies Codex presentation metadata; scripts, references, assets, examples, and hooks stay inside the owning skill. Codex and Claude installations may link to these folders or install snapshots.

The catalog generator reads skill front matter and emits `CATALOG.md` plus `catalog.json`. Validators check metadata, resources, and catalog drift; evaluation fixtures under `evals/skillopt/` exercise optimization and promotion tooling. Python maintenance commands use the repo's uv environment; the catalog generator uses Node.

A maintainer edits a workflow or bundled resource, refreshes the catalog, validates contracts, and inspects the candidate before promotion. Promotion compares candidates to source and applies only through the explicit apply path. Installation then exposes a symlink or copy to an agent host. File validation establishes packaging, not live model, credential, hook, renderer, or external-write readiness.

External connections are skill-specific: Jira reads, release automation, media services, and publishing have separate trust boundaries. The collection does not combine their credentials or grant one skill another skill's authority.
