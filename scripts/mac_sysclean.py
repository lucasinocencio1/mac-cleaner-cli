#!/usr/bin/env python3
# mac_sysclean.py
# A cautious, interactive CLI to inspect & clean macOS "System Data" culprits.
# Run: python3 mac_sysclean.py --interactive  (or --scan, --dry-run)

import os, subprocess, shlex, sys, argparse, pathlib, shutil
from mac_memory import approximate_free_bytes

HOME = str(pathlib.Path.home())

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
    "trash": {
        "type": "paths",
        "desc": "User Trash (~/.Trash)",
        "paths": [f"{HOME}/.Trash"],
        "sudo": False,
        "safe_globs": ["*"],
    },
}

# Targets that require explicit --force to delete
DANGEROUS_KEYS = {"docker_data", "system_caches", "private_tmp"}

def human_size(num):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
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

def size_of_target(key):
    t = TARGETS[key]
    if t["type"] == "special":
        if key == "time_machine_snapshots":
            # We can't sum sizes directly; approximate by "tmutil listlocalsnapshots" count.
            snaps = list_tm_snaps()
            # macOS reclaims space dynamically; we just show count here.
            return f"{len(snaps)} snapshot(s)"
        return "N/A"
    else:
        total = 0
        for p in t["paths"]:
            if os.path.exists(p):
                total += du_path(p)
        return human_size(total)

def run(cmd, need_sudo=False):
    if need_sudo and os.geteuid() != 0:
        cmd = f"sudo {cmd}"
    return subprocess.run(cmd, shell=True)

def list_tm_snaps():
    try:
        out = subprocess.check_output(["tmutil", "listlocalsnapshots", "/"], text=True)
    except subprocess.CalledProcessError:
        return []
    lines = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("com.apple.TimeMachine.")]
    # Extract timestamps
    stamps = []
    for ln in lines:
        parts = ln.rsplit(".", 1)
        if len(parts) == 2:
            stamps.append(parts[1])
    return stamps

def thin_tm_snaps():
    print("→ Deleting local Time Machine snapshots (thinning aggressively)...")
    return run("tmutil thinlocalsnapshots / 9999999999 4", need_sudo=True)

def delete_globs(parent, globs, dry_run=False, need_sudo=False):
    if not os.path.exists(parent):
        return
    for pattern in globs:
        full = os.path.join(parent, pattern)
        for path in pathlib.Path(parent).glob(pattern):
            p = str(path)
            # Safety: ensure we never delete the parent itself with '*' guard
            if os.path.abspath(p) == os.path.abspath(parent):
                continue
            if dry_run:
                print(f"[dry-run] rm -rf {p}")
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
        print(f"[dry-run] rm -rf {path}")
        return
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
    except PermissionError:
        # fallback to shell with sudo
        run(f'rm -rf {shlex.quote(path)}', need_sudo=need_sudo)

def perform_cleanup(selected_keys, dry_run=False):
    for key in selected_keys:
        t = TARGETS[key]
        print(f"\n=== Cleaning: {t['desc']} ===")
        if t["type"] == "special" and key == "time_machine_snapshots":
            if dry_run:
                snaps = list_tm_snaps()
                print(f"[dry-run] Would thin {len(snaps)} snapshot(s).")
            else:
                thin_tm_snaps()
        elif t["type"] == "paths":
            for p in t["paths"]:
                if not os.path.exists(p):
                    continue
                if key == "docker_data" and not DRY_RUN_CONFIRM.get("docker_warned", False):
                    # Just warn that this can remove all Docker images/volumes if user deletes whole folders.
                    print("⚠️  Docker data can be very large and deleting it will remove images/volumes.")
                    DRY_RUN_CONFIRM["docker_warned"] = True
                globs = t.get("safe_globs", [])
                if globs:
                    delete_globs(p, globs, dry_run=dry_run, need_sudo=t.get("sudo", False))
                else:
                    delete_whole_path(p, dry_run=dry_run, need_sudo=t.get("sudo", False))
        print("Done.")

def print_scan():
    print("Scan results (sizes are approximate):\n")
    # show an approximate free memory estimate
    try:
        free = approximate_free_bytes()
        print(f"- Approximate free memory (incl. inactive/speculative): {human_size(free)}")
    except Exception:
        pass
    for key, t in TARGETS.items():
        size = size_of_target(key)
        print(f"- {t['desc']}: {size}")

def prompt_choices():
    keys = list(TARGETS.keys())
    print("\nSelect what to clean (comma-separated numbers). Nothing is deleted without confirmation.\n")
    for i, key in enumerate(keys, 1):
        print(f"{i}) {TARGETS[key]['desc']}")
    print(f"{len(keys)+1}) Everything above")
    choice = input("\nYour choice: ").strip()
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
    ans = input(f"{prompt} [y/N]: ").strip().lower()
    return ans == "y"

DRY_RUN_CONFIRM = {}

def main():
    parser = argparse.ArgumentParser(description="Inspect & clean macOS System Data culprits safely.")
    parser.add_argument("--scan", action="store_true", help="Just scan and report sizes.")
    parser.add_argument("--interactive", action="store_true", help="Scan, then interactively choose what to clean.")
    parser.add_argument("--clean", nargs="*", help="Clean specific keys (e.g., time_machine_snapshots user_caches).")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting.")
    parser.add_argument("--force", action="store_true", help="Force deletion of dangerous targets (required for docker_data, system_caches, private_tmp).")
    args = parser.parse_args()

    if not (args.scan or args.interactive or args.clean):
        parser.print_help()
        sys.exit(0)

    if args.scan or args.interactive or args.clean:
        print_scan()

    selected = []
    if args.interactive:
        selected = prompt_choices()
        if not selected:
            print("No selection. Exiting.")
            sys.exit(0)
    elif args.clean:
        # validate keys
        for k in args.clean:
            if k not in TARGETS:
                print(f"Unknown key: {k}")
                print("Valid keys:", ", ".join(TARGETS.keys()))
                sys.exit(1)
        selected = args.clean

    if selected:
        print("\nYou selected:")
        for k in selected:
            note = ""
            if k in DANGEROUS_KEYS:
                note = " (dangerous: requires --force)"
            print(f"- {TARGETS[k]['desc']}{note}")
        # require --force if any dangerous keys are present
        if any(k in DANGEROUS_KEYS for k in selected) and not args.force:
            print("\nOne or more selected targets are dangerous and require the --force flag to proceed.")
            print("Rerun with --force if you really intend to delete them.")
            sys.exit(1)

        if not confirm("\nProceed with cleanup? (Y/N)"):
            print("Cancelled.")
            sys.exit(0)
        perform_cleanup(selected, dry_run=args.dry_run)
        print("\n✅ Done.")
        print("\nTip: Reclaim space by emptying purgeable storage (if any) and rebooting.")

if __name__ == "__main__":
    main()
