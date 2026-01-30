"""Disk and path helpers for mac-cleaner-cli."""
import os

#size formatter
def human_size(num):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


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
