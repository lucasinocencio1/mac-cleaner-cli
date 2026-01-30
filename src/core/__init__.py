"""Core constants, targets, and config for mac-cleaner-cli."""

from .constants import (
    HOME,
    DOWNLOADS_DIR,
    MAIL_DOWNLOADS,
    NODE_MODULES_SEARCH,
    NODE_MODULES_DAYS_OLD,
    NODE_MODULES_MAX_DEPTH,
    BROWSER_CACHE_PATHS,
    BREW_PATHS,
    BREW_CACHE_PREFIXES,
    DOCKER_PATHS,
)
from .targets import TARGETS, DANGEROUS_KEYS, RISKY_KEYS
from . import config

__all__ = [
    "HOME",
    "DOWNLOADS_DIR",
    "MAIL_DOWNLOADS",
    "NODE_MODULES_SEARCH",
    "NODE_MODULES_DAYS_OLD",
    "NODE_MODULES_MAX_DEPTH",
    "BROWSER_CACHE_PATHS",
    "BREW_PATHS",
    "BREW_CACHE_PREFIXES",
    "DOCKER_PATHS",
    "TARGETS",
    "DANGEROUS_KEYS",
    "RISKY_KEYS",
    "config",
]
