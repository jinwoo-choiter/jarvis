"""Config loader: reads the single committed `config.yaml`.

Non-secret configuration is tracked directly in `config.yaml`. Secrets live
in `.env` (gitignored) and are loaded into the environment by the runner,
not by this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config() -> dict[str, Any]:
    config_path = _repo_root() / "config.yaml"
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
