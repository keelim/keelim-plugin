# Collection status

Observed 2026-10-04: twelve maintained skill folders, generated catalogs, metadata validation, promotion tooling, and SkillOpt evaluation support are present. Existing skill/catalog edits predate this work and remain preserved.

Current evidence covers source layout and declared contracts. Metadata validation passed for all 12 skills with `bash scripts/verify-skills.sh --require-codex-meta`; `scripts/gen-catalog.mjs --check` also passed using the installed Node 24.19.0 binary. These checks establish local metadata and catalog consistency. Live agent discovery, optimizer quality, hooks, credentials, render output, and external publication are separate and were not exercised. Personal installed copies may differ from this checkout; synchronize only through their authorized update paths.

Observed 2026-11-01: `mods/env-guard` and the `keelim-mods` Claude marketplace were added. `claude plugin validate` passed for the mod and the root marketplace on Claude Code 2.1.309, `claude plugin test` passed 7 tests, and `scripts/verify_mods.py` passed. The mod was not installed or loaded into a live session.
