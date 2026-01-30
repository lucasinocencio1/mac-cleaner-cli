#!/usr/bin/env python3
"""Cleanup logic: delete paths, run special cleanups (TM, brew, docker, etc.)."""
import os
import pathlib
import shlex
import shutil
import subprocess

from rich.console import Console
from rich.rule import Rule
from rich.panel import Panel

from ..core.targets import TARGETS
from ..utils.disk import human_size, du_path
from . import scanner_service as scanner

console = Console()


def run(cmd, need_sudo=False):
    if need_sudo and os.geteuid() != 0:
        cmd = f"sudo {cmd}"
    return subprocess.run(cmd, shell=True)


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
                snaps = scanner.list_tm_snaps()
                console.print(f"  [dim]dry-run: Would thin {len(snaps)} snapshot(s).[/]")
            else:
                thin_tm_snaps()
        elif t["type"] == "special" and key == "homebrew":
            brew = scanner._find_brew()
            if not brew:
                console.print("  [yellow]Homebrew not found. Skipping.[/]")
            elif dry_run:
                cache = scanner._brew_cache_path()
                size = du_path(cache) if cache and os.path.exists(cache) else 0
                console.print(f"  [dim]dry-run: Would run brew cleanup --prune=all (approx. {human_size(size)})[/]")
            else:
                console.print("  [cyan]→[/] Running brew cleanup --prune=all...")
                try:
                    subprocess.run([brew, "cleanup", "--prune=all"], check=True, timeout=120)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    console.print(f"  [red]Error: {e}[/]")
        elif t["type"] == "special" and key == "docker_prune":
            docker = scanner._find_docker()
            if not docker:
                console.print("  [yellow]Docker not found or not in PATH. Skipping.[/]")
            elif dry_run:
                b = scanner._docker_reclaimable_bytes()
                console.print(f"  [dim]dry-run: Would run docker system prune -af (reclaimable ~{human_size(b)})[/]")
            else:
                console.print("  [cyan]→[/] Running docker system prune -af (no volumes)...")
                try:
                    subprocess.run([docker, "system", "prune", "-af"], check=True, timeout=300)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    console.print(f"  [red]Error: {e}[/]")
        elif t["type"] == "special" and key == "downloads":
            items = scanner._downloads_old_items()
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
            items = scanner._node_modules_orphans()
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
