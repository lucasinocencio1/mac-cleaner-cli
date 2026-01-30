#!/usr/bin/env python3
"""Command-line interface for mac_cleaner_cli package."""
import json
import os
import re
import subprocess
import time
import shlex
import sys
import argparse
import pathlib
import shutil
from typing import Tuple
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.rule import Rule
from rich.panel import Panel
from .memory import approximate_free_bytes
from . import maintenance
from . import config as config_module

console = Console()

HOME = str(pathlib.Path.home())

DOWNLOADS_DIR = f"{HOME}/Downloads"
MAIL_DOWNLOADS = f"{HOME}/Library/Containers/com.apple.mail/Data/Library/Mail Downloads"
NODE_MODULES_SEARCH = [f"{HOME}/Projects", f"{HOME}/Developer", f"{HOME}/Code", f"{HOME}/dev", f"{HOME}/workspace", f"{HOME}/repos"]
NODE_MODULES_DAYS_OLD = 30
NODE_MODULES_MAX_DEPTH = 4

# Browser cache paths (Chrome, Safari, Firefox, Arc)
BROWSER_CACHE_PATHS = [
    (f"{HOME}/Library/Caches/Google/Chrome", "Chrome"),
    (f"{HOME}/Library/Caches/com.apple.Safari", "Safari"),
    (f"{HOME}/Library/Caches/Firefox", "Firefox"),
    (f"{HOME}/Library/Caches/company.thebrowser.Browser", "Arc"),
]

TARGETS = {
    # label: dict(paths/handlers)
    "time_machine_snapshots": {
        "type": "special",  # handled by tmutil
        "desc": "Local Time Machine snapshots",
    },
    "ios_backups": {
        "type": "paths",
        "desc": "iOS/iPadOS device backups",
        "paths": [f"{HOME}/Library/Application Support/MobileSync/Backup"],
        "sudo": False,
        "safe_globs": ["*"],  # delete children, not parent
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
        "safe_globs": ["blobs/*", "manifests/*"],  # keep folder structure, delete contents
    },
    "docker_data": {
        "type": "paths",
        "desc": "Docker data (~/Library/Containers/com.docker.docker / ~/Docker.raw)",
        "paths": [
            f"{HOME}/Library/Containers/com.docker.docker",
            f"{HOME}/Library/Group Containers/group.com.docker",
            f"{HOME}/Docker.raw"  # older Docker Desktop stores disk image here
        ],
        "sudo": False,
        "safe_globs": [],  # whole path may be large; we won't auto-delete w/o explicit confirm
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

# Targets that require explicit --force to delete
DANGEROUS_KEYS = {"docker_data", "system_caches", "private_tmp"}

# Risky targets: hidden in scan/interactive/clean unless --risky
RISKY_KEYS = DANGEROUS_KEYS | {"ios_backups"}

def human_size(num):
    for unit in ["B", "K", "M", "G", "T"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}P"

def du_path(path):
    total = 0
    try:
        if not os.path.exists(path):
            return 0
        for root, dirs, files in os.walk(path, followlinks=False):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    total += os.path.getsize(fp)
                except Exception:
                    pass
        return total
    except Exception:
        return 0

def count_path(path):
    """Count top-level items (files + dirs) in path. Returns 0 if unreadable."""
    try:
        if not os.path.exists(path):
            return 0
        if os.path.isfile(path):
            return 1
        return len(os.listdir(path))
    except OSError:
        return 0

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

def _bytes_of_target(key):
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
        return human_size(_bytes_of_target(key))
    return human_size(_bytes_of_target(key))

def format_target_size(key):
    """Size string with optional item count, e.g. '2.1 GB (45 items)'."""
    size_str = size_of_target(key)
    if key == "time_machine_snapshots":
        return size_str  # already "N snapshot(s)"
    count = _count_of_target(key)
    if count is not None and count > 0:
        return f"{size_str} ({count} items)"
    return size_str

def run(cmd, need_sudo=False):
    if need_sudo and os.geteuid() != 0:
        cmd = f"sudo {cmd}"
    return subprocess.run(cmd, shell=True)

BREW_PATHS = ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]
BREW_CACHE_PREFIXES = [
    f"{HOME}/Library/Caches/Homebrew",
    "/opt/homebrew/Caches",
    "/usr/local/Caches",
]

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

DOCKER_PATHS = [
    "/usr/local/bin/docker",
    "/opt/homebrew/bin/docker",
    "/Applications/Docker.app/Contents/Resources/bin/docker",
]

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

def thin_tm_snaps():
    console.print("  [cyan]→[/] Deleting local Time Machine snapshots (thinning aggressively)...")
    return run("tmutil thinlocalsnapshots / 9999999999 4", need_sudo=True)

def delete_globs(parent, globs, dry_run=False, need_sudo=False):
    if not os.path.exists(parent):
        return
    for pattern in globs:
        for path in pathlib.Path(parent).glob(pattern):
            p = str(path)
            if os.path.abspath(p) == os.path.abspath(parent):
                continue
            if dry_run:
                console.print(f"  [dim]dry-run: rm -rf {p}[/]")
            else:
                if os.path.isdir(p) and not path.is_symlink():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    try:
                        os.remove(p)
                    except Exception:
                        pass

def delete_whole_path(path, dry_run=False, need_sudo=False):
    if not os.path.exists(path):
        return
    if dry_run:
        console.print(f"  [dim]dry-run: rm -rf {path}[/]")
        return
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
    except PermissionError:
        run(f'rm -rf {shlex.quote(path)}', need_sudo=need_sudo)

def perform_cleanup(selected_keys, dry_run=False):
    console.print()
    console.print(Rule("[bold cyan]Cleaning[/]", style="cyan"))
    for key in selected_keys:
        t = TARGETS[key]
        console.print()
        console.print(Panel(f"[bold]{t['desc']}[/]", style="cyan", border_style="dim", padding=(0, 1)))
        if t["type"] == "special" and key == "time_machine_snapshots":
            if dry_run:
                snaps = list_tm_snaps()
                console.print(f"  [dim]dry-run: Would thin {len(snaps)} snapshot(s).[/]")
            else:
                thin_tm_snaps()
        elif t["type"] == "special" and key == "homebrew":
            brew = _find_brew()
            if not brew:
                console.print("  [yellow]Homebrew not found. Skipping.[/]")
            elif dry_run:
                cache = _brew_cache_path()
                size = du_path(cache) if cache and os.path.exists(cache) else 0
                console.print(f"  [dim]dry-run: Would run brew cleanup --prune=all (approx. {human_size(size)})[/]")
            else:
                console.print("  [cyan]→[/] Running brew cleanup --prune=all...")
                try:
                    subprocess.run([brew, "cleanup", "--prune=all"], check=True, timeout=120)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    console.print(f"  [red]Error: {e}[/]")
        elif t["type"] == "special" and key == "docker_prune":
            docker = _find_docker()
            if not docker:
                console.print("  [yellow]Docker not found or not in PATH. Skipping.[/]")
            elif dry_run:
                b = _docker_reclaimable_bytes()
                console.print(f"  [dim]dry-run: Would run docker system prune -af (reclaimable ~{human_size(b)})[/]")
            else:
                console.print("  [cyan]→[/] Running docker system prune -af (no volumes)...")
                try:
                    subprocess.run([docker, "system", "prune", "-af"], check=True, timeout=300)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    console.print(f"  [red]Error: {e}[/]")
        elif t["type"] == "special" and key == "downloads":
            items = _downloads_old_items()
            if dry_run:
                for p, s in items:
                    console.print(f"  [dim]dry-run: rm -rf {p}[/]")
                console.print(f"  [dim]dry-run: {len(items)} item(s)[/]")
            else:
                for p, _ in items:
                    try:
                        if os.path.isdir(p) and not os.path.islink(p):
                            shutil.rmtree(p, ignore_errors=True)
                        else:
                            os.remove(p)
                    except OSError:
                        pass
        elif t["type"] == "special" and key == "node_modules":
            items = _node_modules_orphans()
            if dry_run:
                for p, _ in items:
                    console.print(f"  [dim]dry-run: rm -rf {p}[/]")
                console.print(f"  [dim]dry-run: {len(items)} node_modules dir(s)[/]")
            else:
                for p, _ in items:
                    try:
                        shutil.rmtree(p, ignore_errors=True)
                    except OSError:
                        pass
        elif t["type"] == "paths":
            for p in t["paths"]:
                if not os.path.exists(p):
                    continue
                if key == "docker_data":
                    console.print("  [yellow]⚠️  Docker data can be very large and deleting it will remove images/volumes.[/]")
                globs = t.get("safe_globs", [])
                if globs:
                    delete_globs(p, globs, dry_run=dry_run, need_sudo=t.get("sudo", False))
                else:
                    delete_whole_path(p, dry_run=dry_run, need_sudo=t.get("sudo", False))
        console.print("  [green]✓ Done.[/]")

def _visible_targets(include_risky: bool) -> Tuple[list, set]:
    """Return (visible keys, exclude set). Loads config once."""
    cfg = config_module.load()
    excl = set(cfg.get("exclude_targets") or [])
    keys = [k for k in TARGETS if k not in excl]
    if not include_risky:
        keys = [k for k in keys if k not in RISKY_KEYS]
    return keys, excl

def print_scan(include_risky: bool = True):
    keys, excl = _visible_targets(include_risky)
    console.print(Rule("[bold cyan]🧹 Mac Cleaner CLI[/]", style="cyan"))
    console.print()
    console.print("[cyan]Scan results (sizes are approximate):[/]\n")
    try:
        free = approximate_free_bytes()
        console.print(f"  [dim]Approximate free memory (incl. inactive/speculative): {human_size(free)}[/]")
    except Exception:
        pass
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Category", style="")
    table.add_column("Size", justify="right", style="yellow")
    for key in keys:
        t = TARGETS[key]
        size = format_target_size(key)
        table.add_row(t["desc"], size)
    console.print(table)
    total_bytes = sum(_bytes_of_target(k) for k in keys)
    console.print()
    console.print(f"  [bold green]Total (approx.): {human_size(total_bytes)} that can be cleaned[/]")
    if not include_risky and RISKY_KEYS:
        hidden = [k for k in RISKY_KEYS if k not in excl and k in TARGETS]
        if hidden:
            console.print(f"\n  [dim yellow]Risky (use --risky to include): {', '.join(hidden)}[/]")
    console.print()

def _prompt_choices_tui(keys: list):
    """Interactive checkbox TUI (space to toggle, enter to confirm). Returns selected keys or None to fallback."""
    try:
        import questionary
        from questionary import Choice
    except ImportError:
        return None
    choices = [Choice(f"{TARGETS[k]['desc']} — {format_target_size(k)}", value=k) for k in keys]
    choices.append(Choice("✓ Select all", value="__all__"))
    msg = "Select categories to clean: SPACE to toggle, ENTER to confirm. Select at least one."
    while True:
        try:
            result = questionary.checkbox(msg, choices=choices).ask()
        except Exception:
            return None
        if result is None:
            return []  # Ctrl+C
        if not result:
            console.print("[yellow]No category selected. Use SPACE to mark categories, then ENTER. Ctrl+C to exit.[/]\n")
            msg = "Select at least one (SPACE to toggle, ENTER to confirm):"
            continue
        if "__all__" in result:
            return keys
        return [v for v in result if v != "__all__"]


def prompt_choices(include_risky: bool = True):
    keys, _ = _visible_targets(include_risky)
    if sys.stdin.isatty():
        selected = _prompt_choices_tui(keys)
        if selected is not None:
            return selected
    console.print()
    console.print("[cyan]Select what to clean (comma-separated numbers). Nothing is deleted without confirmation.[/]\n")
    for i, key in enumerate(keys, 1):
        console.print(f"  [bold]{i})[/] {TARGETS[key]['desc']}")
    console.print(f"  [bold]{len(keys)+1})[/] Everything above")
    choice = console.input("\n[cyan]Your choice: [/]").strip()
    if not choice:
        return []
    if choice == str(len(keys)+1):
        return keys
    idxs = []
    for part in choice.split(","):
        part = part.strip()
        if part.isdigit():
            n = int(part)
            if 1 <= n <= len(keys):
                idxs.append(keys[n-1])
    return idxs

def confirm(prompt):
    # Escape [y/N] so Rich doesn't treat it as markup (style tag)
    ans = console.input(f"[cyan]{prompt} {escape('[y/N]')}: [/]").strip().lower()
    return ans == "y"


def _run_maintenance(dns: bool, purgeable: bool) -> None:
    if not dns and not purgeable:
        console.print("[yellow]No maintenance tasks specified.[/]")
        console.print("[dim]Use --dns to flush DNS cache or --purgeable to free purgeable space.[/]")
        sys.exit(0)
    console.print()
    console.print(Rule("[bold cyan]Maintenance[/]", style="cyan"))
    console.print()
    if dns:
        ok, msg = maintenance.flush_dns_cache()
        if ok:
            console.print(f"  [green]✓[/] {msg}")
        else:
            console.print(f"  [red]✗[/] DNS flush: {msg}")
    if purgeable:
        ok, msg = maintenance.free_purgeable_space()
        if ok:
            console.print(f"  [green]✓[/] {msg}")
        else:
            console.print(f"  [red]✗[/] Purgeable: {msg}")
    console.print()

def _list_categories() -> None:
    console.print(Rule("[bold cyan]🧹 Mac Cleaner CLI — Categories[/]", style="cyan"))
    console.print()
    console.print("[cyan]Available categories (targets):[/]\n")
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Key", style="cyan")
    table.add_column("Description", style="")
    table.add_column("Note", style="dim yellow")
    for key, t in TARGETS.items():
        note = "(dangerous: requires --force)" if key in DANGEROUS_KEYS else ""
        table.add_row(key, t["desc"], note)
    console.print(table)
    console.print()

def _run_config(argv: list) -> None:
    p = argparse.ArgumentParser(prog="mac-sysclean config", description="Manage configuration.")
    p.add_argument("--init", action="store_true", help="Create default config file")
    p.add_argument("--show", action="store_true", help="Show current config")
    args = p.parse_args(argv)
    if args.init:
        path = config_module.init_config()
        console.print(Rule("[bold cyan]Config[/]", style="cyan"))
        console.print()
        console.print(f"  [green]✓[/] Created config at [cyan]{path}[/]")
        console.print()
        return
    if args.show:
        if not config_module.config_exists():
            console.print("[yellow]No config found. Run: mac-sysclean config --init[/]")
            return
        cfg = config_module.load()
        console.print(Rule("[bold cyan]Config[/]", style="cyan"))
        console.print()
        console.print(json.dumps(cfg, indent=2))
        console.print()
        return
    p.print_help()

def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "maintenance":
        p = argparse.ArgumentParser(prog="mac-sysclean maintenance", description="Run maintenance tasks.")
        p.add_argument("--dns", action="store_true", help="Flush DNS cache")
        p.add_argument("--purgeable", action="store_true", help="Free purgeable space")
        args = p.parse_args(argv[1:])
        _run_maintenance(args.dns, args.purgeable)
        return
    if argv and argv[0] == "categories":
        if len(argv) > 1 and argv[1] in ("-h", "--help"):
            console.print("[cyan]Usage:[/] mac-sysclean categories")
            console.print("[dim]List all available cleanup targets.[/]")
            return
        _list_categories()
        return
    if argv and argv[0] == "config":
        _run_config(argv[1:])
        return

    parser = argparse.ArgumentParser(description="Inspect & clean macOS System Data culprits safely.")
    parser.add_argument("--scan", action="store_true", help="Just scan and report sizes.")
    parser.add_argument("--interactive", action="store_true", help="Scan, then interactively choose what to clean.")
    parser.add_argument("--clean", nargs="*", help="Clean specific keys (e.g., time_machine_snapshots user_caches).")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting.")
    parser.add_argument("--force", action="store_true", help="Force deletion of dangerous targets (required for docker_data, system_caches, private_tmp).")
    parser.add_argument("--risky", action="store_true", help="Include risky targets (ios_backups, docker_data, system_caches, private_tmp).")
    args = parser.parse_args(argv)

    if not (args.scan or args.interactive or args.clean):
        parser.print_help()
        console.print("\n[dim]Subcommands: maintenance, categories, config[/]")
        sys.exit(0)

    include_risky = getattr(args, "risky", False)
    if args.scan or args.interactive or args.clean:
        print_scan(include_risky=include_risky)

    selected = []
    if args.interactive:
        selected = prompt_choices(include_risky=include_risky)
        if not selected:
            console.print("[yellow]No selection. Exiting.[/]")
            sys.exit(0)
    elif args.clean:
        cfg = config_module.load()
        excl = set(cfg.get("exclude_targets") or [])
        for k in args.clean:
            if k not in TARGETS:
                console.print(f"[red]Unknown key: {k}[/]")
                console.print(f"[dim]Valid keys: {', '.join(sorted(TARGETS.keys()))}[/]")
                sys.exit(1)
            if k in excl:
                console.print(f"[yellow]{k} is excluded in config. Remove from exclude_targets to clean.[/]")
                sys.exit(1)
            if k in RISKY_KEYS and not include_risky:
                console.print(f"[yellow]{k} is risky. Use --risky to include.[/]")
                sys.exit(1)
        selected = args.clean

    if selected:
        console.print()
        console.print("[bold]You selected:[/]")
        for k in selected:
            note = ""
            if k in DANGEROUS_KEYS:
                note = " [dim yellow](dangerous: requires --force)[/]"
            console.print(f"  • {TARGETS[k]['desc']}{note}")

        if any(k in DANGEROUS_KEYS for k in selected) and not args.force:
            console.print()
            console.print("[red]One or more selected targets are dangerous and require the [bold]--force[/] flag to proceed.[/]")
            console.print("[dim]Rerun with --force if you really intend to delete them.[/]")
            sys.exit(1)

        if not confirm("\nProceed with cleanup?"):
            console.print("[yellow]Cancelled.[/]")
            sys.exit(0)
        perform_cleanup(selected, dry_run=args.dry_run)
        console.print()
        console.print(Rule("[bold green]✓ Done.[/]", style="green"))
        console.print()
        console.print("[dim]Tip: Reclaim space by emptying purgeable storage (if any) and rebooting.[/]")
        console.print()

if __name__ == "__main__":
    main()
