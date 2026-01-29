# Documentation

Design notes, comparisons, and architecture docs live here.

- Add `COMPARISON_TS_VS_PYTHON.md` or similar for cross-project notes.
- Use this folder for non-README documentation (ADR, specs, etc.).

## Duplication / code hygiene

- **`scripts/legacy/`** duplicates the main package (`mac_memory` ≈ `mac_cleaner_cli.memory`; `mac_sysclean` ≈ older `cli`). Kept for reference only.
- **Config loading:** `config.load()` is still called in several places per run (`_visible_targets`, `_downloads_old_items`, `--clean` validation). Consider a per-run cache or passing `cfg` through if it becomes a concern.
- **`run` (cli) vs `_run_cmd` (maintenance):** Different use cases (shell vs list-args, return shape). No current duplication; could be unified in a shared util later if desired.
