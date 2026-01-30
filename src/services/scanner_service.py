#!/usr/bin/env python3
"""Scan/size logic: target bytes, counts, format, visible keys."""
import os
import re
import subprocess
import time
from typing import Tuple

from ..core import config as config_module
from ..core.constants import (
    DOWNLOADS_DIR,
    NODE_MODULES_DAYS_OLD,
    NODE_MODULES_MAX_DEPTH,
    NODE_MODULES_SEARCH,
    BREW_PATHS,
    BREW_CACHE_PREFIXES,
    DOCKER_PATHS,
)
from ..core.targets import TARGETS, RISKY_KEYS
from ..utils.disk import human_size, du_path, count_path


def _find_brew():
    for p in BREW_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def _brew_cache_path():
    brew = _find_brew()
    if not brew:
        return None
    try:
        out = subprocess.check_output([brew, "--cache"], text=True, timeout=10)
        path = out.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    path = os.path.abspath(path)
    for prefix in BREW_CACHE_PREFIXES:
        if path == prefix or path.startswith(prefix + os.sep):
            return path
    return None


def _find_docker():
    for p in DOCKER_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def _parse_docker_size(s: str) -> int:
    s = (s or "").strip()
    m = re.match(r"([\d.]+)\s*(B|KB|MB|GB|TB|kB)", s, re.I)
    if not m:
        return 0
    val = float(m.group(1))
    u = (m.group(2) or "").upper()
    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return int(val * mult.get(u, 1))


def _docker_reclaimable_bytes() -> int:
    docker = _find_docker()
    if not docker:
        return 0
    try:
        out = subprocess.check_output(
            [docker, "system", "df", "--format", "{{.Type}}\t{{.Size}}\t{{.Reclaimable}}"],
            text=True,
            timeout=30,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return 0
    total = 0
    valid = {"images", "containers", "local volumes", "build cache"}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        kind = (parts[0] or "").strip().lower()
        if kind not in valid:
            continue
        total += _parse_docker_size(parts[2])
    return total


def _downloads_old_items():
    """Return [(path, size), ...] for top-level items in ~/Downloads older than config days."""
    out = []
    if not os.path.isdir(DOWNLOADS_DIR):
        return out
    cfg = config_module.load()
    days = int(cfg.get("downloads_days_old") or 30)
    cutoff = time.time() - days * 86400
    try:
        for name in os.listdir(DOWNLOADS_DIR):
            if name.startswith("."):
                continue
            p = os.path.join(DOWNLOADS_DIR, name)
            try:
                st = os.stat(p, follow_symlinks=False)
                if st.st_mtime >= cutoff:
                    continue
                size = du_path(p) if os.path.isdir(p) else st.st_size
                out.append((p, size))
            except OSError:
                pass
    except OSError:
        pass
    return out


def _node_modules_orphans():
    """Return [(path, size), ...] for orphan or old node_modules in search dirs."""
    out = []
    cutoff = time.time() - NODE_MODULES_DAYS_OLD * 86400
    seen = set()

    def scan(dirpath, depth):
        if depth > NODE_MODULES_MAX_DEPTH:
            return
        try:
            for name in os.listdir(dirpath):
                if name.startswith("."):
                    continue
                full = os.path.join(dirpath, name)
                try:
                    if not os.path.isdir(full) or os.path.islink(full):
                        continue
                    if name == "node_modules":
                        if full in seen:
                            continue
                        seen.add(full)
                        parent = dirpath
                        pkg = os.path.join(parent, "package.json")
                        orphan = not os.path.isfile(pkg)
                        try:
                            parent_mtime = os.path.getmtime(parent)
                        except OSError:
                            parent_mtime = 0
                        old = parent_mtime < cutoff
                        if orphan or old:
                            sz = du_path(full)
                            out.append((full, sz))
                        continue
                    scan(full, depth + 1)
                except OSError:
                    pass
        except OSError:
            pass

    for d in NODE_MODULES_SEARCH:
        if os.path.isdir(d):
            scan(d, 0)
    return out


def list_tm_snaps():
    try:
        out = subprocess.check_output(["tmutil", "listlocalsnapshots", "/"], text=True)
    except subprocess.CalledProcessError:
        return []
    lines = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("com.apple.TimeMachine.")]
    stamps = []
    for ln in lines:
        parts = ln.rsplit(".", 1)
        if len(parts) == 2:
            stamps.append(parts[1])
    return stamps


def _count_of_target(key):
    """Return number of items for target (top-level per path, or special logic). None if not applicable."""
    t = TARGETS[key]
    if t["type"] == "special":
        if key == "time_machine_snapshots":
            return len(list_tm_snaps())
        if key == "homebrew":
            cache = _brew_cache_path()
            return count_path(cache) if cache and os.path.exists(cache) else None
        if key == "docker_prune":
            return None
        if key == "downloads":
            return len(_downloads_old_items())
        if key == "node_modules":
            return len(_node_modules_orphans())
        return None
    total = 0
    for p in t["paths"]:
        total += count_path(p)
    return total if total else None


def bytes_of_target(key):
    """Return approximate size in bytes for a target. TM snapshots → 0 (unknown)."""
    t = TARGETS[key]
    if t["type"] == "special":
        if key == "time_machine_snapshots":
            return 0
        if key == "homebrew":
            cache = _brew_cache_path()
            return du_path(cache) if cache and os.path.exists(cache) else 0
        if key == "docker_prune":
            return _docker_reclaimable_bytes()
        if key == "downloads":
            return sum(s for _, s in _downloads_old_items())
        if key == "node_modules":
            return sum(s for _, s in _node_modules_orphans())
        return 0
    total = 0
    for p in t["paths"]:
        if os.path.exists(p):
            total += du_path(p)
    return total


def size_of_target(key):
    t = TARGETS[key]
    if t["type"] == "special":
        if key == "time_machine_snapshots":
            snaps = list_tm_snaps()
            return f"{len(snaps)} snapshot(s)"
        return human_size(bytes_of_target(key))
    return human_size(bytes_of_target(key))


def format_target_size(key):
    """Size string with optional item count, e.g. '2.1 GB (45 items)'."""
    size_str = size_of_target(key)
    if key == "time_machine_snapshots":
        return size_str
    count = _count_of_target(key)
    if count is not None and count > 0:
        return f"{size_str} ({count} items)"
    return size_str


def count_of_target(key):
    """Public alias for _count_of_target."""
    return _count_of_target(key)


def visible_targets(include_risky: bool) -> Tuple[list, set]:
    """Return (visible keys, exclude set). Loads config once."""
    cfg = config_module.load()
    excl = set(cfg.get("exclude_targets") or [])
    keys = [k for k in TARGETS if k not in excl]
    if not include_risky:
        keys = [k for k in keys if k not in RISKY_KEYS]
    return keys, excl
