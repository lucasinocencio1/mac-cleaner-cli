#!/usr/bin/env python3
"""Command-line interface for mac-cleaner-cli (src package)."""
import json
import sys
import argparse

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.rule import Rule
from rich.panel import Panel

from .utils.memory import approximate_free_bytes
from .utils.disk import human_size
from .services import maintenance
from .services import scanner_service as scanner
from .services import cleanup_service as cleanup
from .core import config as config_module
from .core.targets import TARGETS, DANGEROUS_KEYS, RISKY_KEYS

console = Console()


def print_scan(include_risky: bool = True):
    keys, excl = scanner.visible_targets(include_risky)
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
        size = scanner.format_target_size(key)
        table.add_row(t["desc"], size)
    console.print(table)
    total_bytes = sum(scanner.bytes_of_target(k) for k in keys)
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
    choices = [Choice(f"{TARGETS[k]['desc']} — {scanner.format_target_size(k)}", value=k) for k in keys]
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
    """Prompt the user for choices."""
    keys, _ = scanner.visible_targets(include_risky)
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
    """Confirm the user's choice."""
    # Escape [y/N] so Rich doesn't treat it as markup (style tag)
    ans = console.input(f"[cyan]{prompt} {escape('[y/N]')}: [/]").strip().lower()
    return ans == "y"


def _run_maintenance(dns: bool, purgeable: bool) -> None:
    """Run the maintenance tasks."""
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
    """List the categories."""
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
    """Run the configuration tasks."""
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
    """Main function."""
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
        total_items = sum(c for k in selected for c in (scanner.count_of_target(k),) if c is not None)
        total_bytes = sum(scanner.bytes_of_target(k) for k in selected)
        console.print("[bold]Summary:[/]") # here we add the summary of the total items and space to free
        console.print(f"  Items to delete: {total_items}")
        console.print(f"  Space to free: {human_size(total_bytes)}")
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
        cleanup.perform_cleanup(selected, dry_run=args.dry_run)
        console.print()
        console.print(Rule("[bold green]✓ Done.[/]", style="green"))
        console.print()
        console.print("[dim]Tip: Reclaim space by emptying purgeable storage (if any) and rebooting.[/]")
        console.print()

if __name__ == "__main__":
    main()
