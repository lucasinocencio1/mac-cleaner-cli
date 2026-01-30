"""Cleanup targets and key sets for mac-cleaner-cli."""

from .constants import (
    HOME,
    MAIL_DOWNLOADS,
    BROWSER_CACHE_PATHS,
)

TARGETS = {
    "time_machine_snapshots": {
        "type": "special",
        "desc": "Local Time Machine snapshots",
    },
    "ios_backups": {
        "type": "paths",
        "desc": "iOS/iPadOS device backups",
        "paths": [f"{HOME}/Library/Application Support/MobileSync/Backup"],
        "sudo": False,
        "safe_globs": ["*"],
    },
    "xcode_derived": {
        "type": "paths",
        "desc": "Xcode DerivedData",
        "paths": [f"{HOME}/Library/Developer/Xcode/DerivedData"],
        "sudo": False,
        "safe_globs": ["*"],
    },
    "xcode_archives": {
        "type": "paths",
        "desc": "Xcode Archives",
        "paths": [f"{HOME}/Library/Developer/Xcode/Archives"],
        "sudo": False,
        "safe_globs": ["*"],
    },
    "system_caches": {
        "type": "paths",
        "desc": "System caches (/Library/Caches)",
        "paths": ["/Library/Caches"],
        "sudo": True,
        "safe_globs": ["*"],
    },
    "user_caches": {
        "type": "paths",
        "desc": "User caches (~/Library/Caches)",
        "paths": [f"{HOME}/Library/Caches"],
        "sudo": False,
        "safe_globs": ["*"],
    },
    "browser_cache": {
        "type": "paths",
        "desc": "Browser cache (Chrome, Safari, Firefox, Arc)",
        "paths": [p[0] for p in BROWSER_CACHE_PATHS],
        "sudo": False,
        "safe_globs": ["*"],
    },
    "homebrew": {
        "type": "special",
        "desc": "Homebrew cache (brew cleanup --prune=all)",
    },
    "system_logs": {
        "type": "paths",
        "desc": "System logs (/private/var/log)",
        "paths": ["/private/var/log"],
        "sudo": True,
        "safe_globs": ["*"],
    },
    "user_logs": {
        "type": "paths",
        "desc": "User logs (~/Library/Logs)",
        "paths": [f"{HOME}/Library/Logs"],
        "sudo": False,
        "safe_globs": ["*"],
    },
    "private_tmp": {
        "type": "paths",
        "desc": "System temp (/private/tmp and /private/var/tmp)",
        "paths": ["/private/tmp", "/private/var/tmp"],
        "sudo": True,
        "safe_globs": ["*"],
    },
    "ollama_models": {
        "type": "paths",
        "desc": "Ollama models (~/.ollama/models)",
        "paths": [f"{HOME}/.ollama/models"],
        "sudo": False,
        "safe_globs": ["blobs/*", "manifests/*"],
    },
    "docker_data": {
        "type": "paths",
        "desc": "Docker data (~/Library/Containers/com.docker.docker / ~/Docker.raw)",
        "paths": [
            f"{HOME}/Library/Containers/com.docker.docker",
            f"{HOME}/Library/Group Containers/group.com.docker",
            f"{HOME}/Docker.raw",
        ],
        "sudo": False,
        "safe_globs": [],
    },
    "docker_prune": {
        "type": "special",
        "desc": "Docker reclaimable (docker system prune -af, no volumes)",
    },
    "trash": {
        "type": "paths",
        "desc": "User Trash (~/.Trash)",
        "paths": [f"{HOME}/.Trash"],
        "sudo": False,
        "safe_globs": ["*"],
    },
    "downloads": {
        "type": "special",
        "desc": "Old Downloads (~/Downloads, older than N days)",
    },
    "mail_attachments": {
        "type": "paths",
        "desc": "Mail.app attachments (Mail Downloads)",
        "paths": [MAIL_DOWNLOADS],
        "sudo": False,
        "safe_globs": ["*"],
    },
    "node_modules": {
        "type": "special",
        "desc": "Orphan/old node_modules (Projects, Developer, etc.)",
    },
}

DANGEROUS_KEYS = {"docker_data", "system_caches", "private_tmp"}
RISKY_KEYS = DANGEROUS_KEYS | {"ios_backups"}
