"""Role-note storage used by agent decisions and feedback review."""
from typing import Protocol
from .models import MemoryRole, RoleNote


class MemoryProtocol(Protocol):
    def recall(self, role: MemoryRole) -> RoleNote: ...
    def apply(self, before: RoleNote, content: str, event_id: str) -> bool:
        """Commit a revision once. Return False if its base changed."""
        ...
