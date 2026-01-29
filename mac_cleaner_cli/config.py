#!/usr/bin/env python3
"""Configuration for mac_cleaner_cli."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

HOME = str(Path.home())
CONFIG_PATHS = [
    os.path.join(HOME, ".maccleanerrc"),
    os.path.join(HOME, ".config", "mac-cleaner-cli", "config.json"),
]

DEFAULTS: dict[str, Any] = {
    "exclude_targets": [],
    "downloads_days_old": 30,
    "large_files_mb": 500,
    "backup_retention_days": 7,
}

VALID_KEYS = frozenset(DEFAULTS.keys())


def config_path() -> str:
    """Preferred config file path (create dirs if needed)."""
    return CONFIG_PATHS[0]


def config_exists() -> bool:
    """True if any known config file exists."""
    for p in CONFIG_PATHS:
        if os.path.isfile(p):
            return True
    return False


def load() -> dict[str, Any]:
    """Load config from first existing file. Returns defaults + overrides."""
    out = dict(DEFAULTS)
    for p in CONFIG_PATHS:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                continue
            for k, v in raw.items():
                if k not in VALID_KEYS:
                    continue
                if k == "exclude_targets" and isinstance(v, list):
                    out[k] = [str(x) for x in v if isinstance(x, str)][:200]
                elif k == "downloads_days_old" and isinstance(v, (int, float)):
                    val = int(v)
                    if 1 <= val <= 365:
                        out[k] = val
                elif k == "large_files_mb" and isinstance(v, (int, float)):
                    val = int(v)
                    if 1 <= val <= 100 * 1024:  # up to 100GB
                        out[k] = val
                elif k == "backup_retention_days" and isinstance(v, (int, float)):
                    val = int(v)
                    if 1 <= val <= 365:
                        out[k] = val
            return out
        except (OSError, json.JSONDecodeError):
            continue
    return out


def save(cfg: dict[str, Any], path: str | None = None) -> None:
    """Write config to path (default: config_path()). Creates parent dirs."""
    p = path or config_path()
    dirname = os.path.dirname(p)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    to_write = {k: cfg.get(k, DEFAULTS[k]) for k in VALID_KEYS}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(to_write, f, indent=2)


def init_config() -> str:
    """Create default config file. Returns path used."""
    p = config_path()
    save(DEFAULTS, p)
    return p
