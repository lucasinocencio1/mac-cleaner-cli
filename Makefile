# mac-cleaner-cli — Makefile
# Usage: make [target]. List commands: make help

PYTHON  ?= python3
CLI     := $(PYTHON) -m src.cli

.PHONY: help install test scan interactive categories maintenance-dns maintenance-purge config-init config-show clean-dry

help:
	@echo "mac-cleaner-cli — available commands:"
	@echo ""
	@echo "  make install             Install package (pip install -e .)"
	@echo "  make test                Run tests (unittest)"
	@echo "  make scan                Run scan (approximate sizes)"
	@echo "  make interactive         Interactive mode (scan + TUI to choose what to clean)"
	@echo "  make categories          List all categories (targets)"
	@echo "  make maintenance-dns     Flush DNS cache (may require sudo)"
	@echo "  make maintenance-purge   Free purgeable space (may require sudo)"
	@echo "  make config-init         Create config at ~/.maccleanerrc"
	@echo "  make config-show         Show current config"
	@echo "  make clean-dry           Dry-run: user_caches + trash (example)"
	@echo ""
	@echo "Examples:"
	@echo "  make scan"
	@echo "  make scan RISKY=1        Include risky targets (--risky)"
	@echo "  make clean-dry TARGETS='user_caches browser_cache'"

install:
	@$(PYTHON) -m pip install -e .

test:
	@$(PYTHON) -m unittest discover -s tests -v

scan:
	@if [ "$(RISKY)" = "1" ]; then $(CLI) --scan --risky; else $(CLI) --scan; fi

interactive:
	@if [ "$(RISKY)" = "1" ]; then $(CLI) --interactive --risky; else $(CLI) --interactive; fi

categories:
	@$(CLI) categories

maintenance-dns:
	@$(CLI) maintenance --dns

maintenance-purge:
	@$(CLI) maintenance --purgeable

config-init:
	@$(CLI) config --init

config-show:
	@$(CLI) config --show

clean-dry:
	@$(CLI) --clean $(or $(TARGETS),user_caches trash) --dry-run
