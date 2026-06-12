"""Dataloader for redacted plugin skill improvement examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from skillopt.datasets.base import SplitDataLoader
except Exception:  # pragma: no cover - used before SkillOpt is installed
    class SplitDataLoader:  # type: ignore[no-redef]
        def load_raw_items(self, data_path: str) -> list[dict[str, Any]]:
            raise NotImplementedError


def load_items(path: str | Path) -> list[dict[str, Any]]:
    data_path = Path(path)
    text = data_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("items")
        if isinstance(data, list):
            return data
    raise ValueError(f"Unsupported plugin skill item file: {data_path}")


class PluginSkillImproverDataLoader(SplitDataLoader):
    """SkillOpt split loader for `train/val/test/items.json` data."""

    def load_raw_items(self, data_path: str) -> list[dict[str, Any]]:
        return load_items(data_path)
