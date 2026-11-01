# Claude Code mods

Each `mods/<name>/` is an opt-in Claude Code plugin of function hooks: `.claude-plugin/plugin.json`, `hooks/hooks.json` naming one hooks module, that module, and `tests/*.test.ts`. Mods never join the skills-only root package, and the root never gains `.claude-plugin/plugin.json` or `hooks/hooks.json`.

`.claude-plugin/marketplace.json` (`keelim-mods`) lists every mod as `./mods/<name>`; `scripts/verify_mods.py` fails on an unlisted mod, a mismatched name, or a hooks module outside its mod. The function-hook API is early access: the declarations Claude Code writes beside a loaded mod (`.claude-plugin/types/`, ignored) are the contract for that build.

## Effects

Declare each mod's effects here, as skills declare theirs in front matter. A mod's hooks run on every matching event once installed; installing one is a hook installation (`docs/security.md`).

| Mod | hooks | Effect |
| --- | --- | --- |
| `env-guard` | true | Denies Read, Edit, and Write on `.env` and `.env.*` paths; fails closed when its guard throws; no network, files, or state |

## Develop and verify

```sh
claude plugin validate mods/<name>    # manifest and hooks module as the engine reads them
claude plugin test mods/<name>        # tests/*.test.ts against the engine (claude-code/testing)
python3 scripts/verify_mods.py        # offline marketplace/layout check; also run by scripts/check.sh
claude --plugin-dir mods/<name> --debug   # load for one session; saves hot-reload
```

`validate` and `test` need the Claude Code CLI and are local checks; CI runs only `verify_mods.py`. Neither establishes behaviour in a live session. Keep matchers literal (`{ tool: 'Edit' }`) so `validate` lists what each hook gates, and give a gating hook a `.catch` that denies when its own `next` was not called.

## Install (explicit, per mod)

```
/plugin install env-guard --marketplace keelim/keelim-plugin
```

From a checkout, `claude plugin marketplace add <repo folder>` reads mods from this folder; `/reload-plugins` picks up edits.
