"""Deterministic evaluator for plugin skill improvement responses."""

from __future__ import annotations

import re
from typing import Any


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _contains(haystack: str, needle: str) -> bool:
    return normalize_text(needle) in haystack


def evaluate(response: str, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    expected = expected or {}
    normalized = normalize_text(response)
    must_find = [str(item) for item in expected.get("must_find", [])]
    forbidden = [
        str(item)
        for group in ("must_not_claim", "must_not_do")
        for item in expected.get(group, [])
    ]

    found = [item for item in must_find if _contains(normalized, item)]
    missing = [item for item in must_find if item not in found]
    violations = [item for item in forbidden if _contains(normalized, item)]

    required_fraction = len(found) / len(must_find) if must_find else 1.0
    no_forbidden = 1.0 if not violations else 0.0
    hard = int(required_fraction == 1.0 and no_forbidden == 1.0)
    soft = round((0.8 * required_fraction) + (0.2 * no_forbidden), 4)
    return {
        "hard": hard,
        "soft": soft,
        "found": found,
        "missing": missing,
        "violations": violations,
        "required_fraction": round(required_fraction, 4),
        "no_forbidden": bool(no_forbidden),
    }
