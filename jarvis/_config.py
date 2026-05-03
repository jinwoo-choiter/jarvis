"""Config loader: merges committed `config.yaml` with optional `config.local.yaml`.

`config.local.yaml` is gitignored. Any top-level key in the local file
fully replaces the same key from `config.yaml`. Nested merging is intentionally
not performed — the local file is the source of truth when present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config() -> dict[str, Any]:
    root = _repo_root()
    base_path = root / "config.yaml"
    local_path = root / "config.local.yaml"

    base: dict[str, Any] = {}
    if base_path.exists():
        with base_path.open("r", encoding="utf-8") as f:
            base = yaml.safe_load(f) or {}

    if local_path.exists():
        with local_path.open("r", encoding="utf-8") as f:
            local = yaml.safe_load(f) or {}
        base.update(local)

    return base
