#!/usr/bin/env python3
"""Maintenance tasks: flush DNS cache, free purgeable space."""
import os
import subprocess
from typing import Tuple


def _run_cmd(args: list, timeout: int = 10) -> Tuple[bool, str]:
    """Run command with list args (no shell). Returns (success, error_message)."""
    try:
        subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        return True, ""
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip() or f"exit code {e.returncode}"
        return False, err
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, str(e)


def _can_sudo_nopasswd() -> bool:
    """Check if sudo works without password (non-interactive)."""
    ok, _ = _run_cmd(["sudo", "-n", "true"], timeout=5)
    return ok


def flush_dns_cache() -> Tuple[bool, str]:
    """
    Flush macOS DNS cache (dscacheutil + mDNSResponder).
    May require sudo. Returns (success, message).
    """
    is_root = os.geteuid() == 0
    if not is_root and not _can_sudo_nopasswd():
        return False, "Requires sudo. Run: sudo mac-sysclean maintenance --dns"

    prefix = [] if is_root else ["sudo", "-n"]
    ok1, err1 = _run_cmd(prefix + ["/usr/bin/dscacheutil", "-flushcache"])
    if not ok1:
        e = err1 or "dscacheutil failed"
        if "Operation not permitted" in e or "Permission denied" in e:
            return False, "Requires sudo. Run: sudo mac-sysclean maintenance --dns"
        return False, e
    ok2, err2 = _run_cmd(prefix + ["/usr/bin/killall", "-HUP", "mDNSResponder"])
    if not ok2:
        e = err2 or "killall mDNSResponder failed"
        if "Operation not permitted" in e or "Permission denied" in e:
            return False, "Requires sudo. Run: sudo mac-sysclean maintenance --dns"
        return False, e
    return True, "DNS cache flushed successfully"


def free_purgeable_space() -> Tuple[bool, str]:
    """
    Free purgeable disk space via /usr/sbin/purge.
    May require sudo. Returns (success, message).
    """
    purge_path = "/usr/sbin/purge"
    is_root = os.geteuid() == 0

    if is_root:
        ok, err = _run_cmd([purge_path], timeout=60)
    else:
        ok, err = _run_cmd(["sudo", "-n", purge_path], timeout=60)
    if ok:
        return True, "Purgeable space freed successfully"

    # Try without sudo (sometimes works)
    ok2, err2 = _run_cmd([purge_path], timeout=60)
    if ok2:
        return True, "Purgeable space freed successfully"

    err_combined = (err or "") + (err2 or "")
    if "Operation not permitted" in err_combined or "Permission denied" in err_combined or "sudo" in err_combined.lower():
        return False, "Requires sudo. Run: sudo mac-sysclean maintenance --purgeable"
    return False, err or err2 or "purge failed"
