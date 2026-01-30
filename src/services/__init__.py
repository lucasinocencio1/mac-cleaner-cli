"""Services (business logic) for mac-cleaner-cli."""

from . import maintenance_service
from . import scanner_service
from . import cleanup_service

maintenance = maintenance_service  # backward compat

__all__ = ["maintenance", "maintenance_service", "scanner_service", "cleanup_service"]
