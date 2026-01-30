"""mac-cleaner-cli package (src)."""

from . import utils
from . import services
from . import core
from .utils import memory
from .services import maintenance
from .core import config

__all__ = ["cli", "config", "memory", "maintenance", "core", "utils", "services"]
