#!/usr/bin/env python3
"""Helpers to inspect macOS memory and purgeable space."""
import subprocess
from typing import Dict

def vm_stat_summary() -> Dict[str,int]:
    try:
        out = subprocess.check_output(["vm_stat"], text=True)
    except Exception:
        return {}
    res = {}
    for line in out.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().replace(".", "")
            try:
                res[key] = int(val.split()[0])
            except Exception:
                pass
    return res

def approximate_free_bytes() -> int:
    # Use vm_stat to estimate free + inactive pages (approx)
    data = vm_stat_summary()
    page_size = 4096
    free = data.get("Pages free", 0)
    inactive = data.get("Pages inactive", 0)
    speculative = data.get("Pages speculative", 0)
    return (free + inactive + speculative) * page_size
