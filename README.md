mac-cleaner-cli

An open-source CLI to inspect and clean macOS System Data.

Makefile (shortcuts)

From the project root, `make` or `make help` lists all commands. Examples:

```bash
make help              # List all targets
make install           # pip install -e .
make test              # Run tests (unittest)
make scan              # --scan
make scan RISKY=1      # --scan --risky
make interactive       # Interactive mode
make categories        # List categories
make maintenance-dns   # maintenance --dns
make maintenance-purge # maintenance --purgeable
make config-init       # config --init
make config-show       # config --show
make clean-dry         # Dry-run user_caches + trash
make clean-dry TARGETS='user_caches browser_cache'   # Dry-run with specific targets
```

Safety and notes

- This tool is intentionally conservative: nothing is deleted without explicit confirmation.
- Some operations require `sudo` (e.g., system caches); the tool will fallback to `sudo` when needed.
- Always review what will be deleted using `--dry-run` before running for real.
- The `time_machine_snapshots` handler uses `tmutil thinlocalsnapshots` to request macOS reclaim space.

- Dangerous targets: `docker_data`, `system_caches`, and `private_tmp` can remove large amounts of data and require `--force` to actually delete. The tool will refuse to run deletions of these targets unless `--force` is passed.

- **`--risky`:** Include risky targets (e.g. `ios_backups`, `docker_data`, `system_caches`, `private_tmp`) in scan/interactive/clean. Without `--risky`, they are hidden.

- **Config:** `mac-sysclean config --init` creates `~/.maccleanerrc`; `config --show` prints current config. Options include `exclude_targets`, `downloads_days_old`, `large_files_mb`, `backup_retention_days`.

- **Targets:** `browser_cache`, `homebrew`, `docker_prune` (Docker reclaimable, no volumes), `downloads` (old files in `~/Downloads`, configurable via `downloads_days_old`), `mail_attachments` (Mail.app Mail Downloads), `node_modules` (orphan/old in Projects, Developer, etc.). Use `categories` to list all.

- **Terminal UI:** The CLI uses [Rich](https://github.com/Textualize/rich) for colored output, tables, rules, and panels (similar to the TypeScript version). Install with `pip install -e .` (or `pip install rich`).

Contributing

Feel free to open issues or PRs to add more targets or improves.
