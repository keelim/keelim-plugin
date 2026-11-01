# Mods as separate opt-in plugins

## Context

Claude Code mods are function-hook plugins that run on every matching event once installed. The root package is a skills-only portable plugin shared with Codex, and `scripts/verify_plugin.py` rejects root hooks.

## Decision and alternatives

Keep each mod in `mods/<name>/` as its own plugin, listed by a mods-only Claude marketplace at `.claude-plugin/marketplace.json`. Adding hooks to the root package was rejected: installing skills would silently install hooks for every host.

## Consequences

Each mod is installed explicitly and declares its effects in `mods/AGENTS.md`. `claude plugin validate .` at the root now reads the marketplace; the skills package keeps `verify_plugin.py` as its contract. Engine checks need the Claude Code CLI; CI covers layout through `verify_mods.py`.
