"""Path and tool constants for mac-cleaner-cli."""

import pathlib

HOME = str(pathlib.Path.home())

DOWNLOADS_DIR = f"{HOME}/Downloads"
MAIL_DOWNLOADS = f"{HOME}/Library/Containers/com.apple.mail/Data/Library/Mail Downloads"
NODE_MODULES_SEARCH = [
    f"{HOME}/Projects",
    f"{HOME}/Developer",
    f"{HOME}/Code",
    f"{HOME}/dev",
    f"{HOME}/workspace",
    f"{HOME}/repos",
]
NODE_MODULES_DAYS_OLD = 30
NODE_MODULES_MAX_DEPTH = 4

# Browser cache paths (Chrome, Safari, Firefox, Arc)
BROWSER_CACHE_PATHS = [
    (f"{HOME}/Library/Caches/Google/Chrome", "Chrome"),
    (f"{HOME}/Library/Caches/com.apple.Safari", "Safari"),
    (f"{HOME}/Library/Caches/Firefox", "Firefox"),
    (f"{HOME}/Library/Caches/company.thebrowser.Browser", "Arc"),
]

BREW_PATHS = ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]
BREW_CACHE_PREFIXES = [
    f"{HOME}/Library/Caches/Homebrew",
    "/opt/homebrew/Caches",
    "/usr/local/Caches",
]

DOCKER_PATHS = [
    "/usr/local/bin/docker",
    "/opt/homebrew/bin/docker",
    "/Applications/Docker.app/Contents/Resources/bin/docker",
]
