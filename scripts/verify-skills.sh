#!/usr/bin/env bash
# W2-plugin-01 — skill smoke-test harness.
#
# Verifies each skills/<name> has the required files and metadata, that the
# frontmatter name matches the folder, that the skill is documented in README,
# and reports Codex/Claude install parity (agents/openai.yaml presence).
#
# Exit 0 when all skills are structurally valid; exit 1 on any defect.

set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
count=0
for d in skills/*/; do
  name="$(basename "$d")"
  count=$((count + 1))
  skill="${d}SKILL.md"

  if [ ! -f "$skill" ]; then
    echo "[fail] ${name}: missing SKILL.md"
    fail=1
    continue
  fi

  # Frontmatter block (between the first two '---' lines).
  fm="$(awk '/^---[[:space:]]*$/{c++; next} c==1{print} c>=2{exit}' "$skill")"
  if ! grep -qE '^name:' <<<"$fm"; then echo "[fail] ${name}: frontmatter missing name"; fail=1; fi
  if ! grep -qE '^description:' <<<"$fm"; then echo "[fail] ${name}: frontmatter missing description"; fail=1; fi

  fmname="$(sed -nE 's/^name:[[:space:]]*//p' <<<"$fm" | tr -d "\"'" | head -1)"
  if [ "$fmname" != "$name" ]; then echo "[fail] ${name}: frontmatter name '${fmname}' != folder"; fail=1; fi

  # Body must be non-trivial (skip the frontmatter, count non-empty lines).
  body_lines="$(sed '1,/^---[[:space:]]*$/d; 1,/^---[[:space:]]*$/d' "$skill" | grep -cve '^[[:space:]]*$' || true)"
  if [ "${body_lines:-0}" -lt 3 ]; then echo "[fail] ${name}: SKILL.md body too short (${body_lines} lines)"; fail=1; fi

  # README must document the skill (install discoverability).
  if ! grep -qF "\`${name}\`" README.md; then echo "[fail] ${name}: not listed in README"; fail=1; fi

  # Codex/Claude parity (informational): openai.yaml = Codex agent metadata present.
  if [ -f "${d}agents/openai.yaml" ]; then parity="codex+claude"; else parity="claude-only"; fi
  echo "[ok] ${name} (${parity})"
done

echo "[verify-skills] checked ${count} skills"
if [ "$fail" -ne 0 ]; then
  echo "[verify-skills] FAIL"
  exit 1
fi
echo "[verify-skills] OK"
