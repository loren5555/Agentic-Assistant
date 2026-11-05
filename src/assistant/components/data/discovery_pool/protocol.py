"""Storage contract for the bounded, human-browsable discovery cache."""

from typing import Protocol
from assistant.components.data.discovery_pool.models import DiscoveryEntry
from assistant.components.recommendations.discovery.models import PaperCandidate


class DiscoveryPoolProtocol(Protocol):
    """Retain search results before expensive reading and recommendation."""

    def initialize_schema(self) -> None:
        """Prepare or locate the Assistant-owned discovery database."""
        ...

    def refresh(self, candidates: list[PaperCandidate], day: str, limit: int) -> list[DiscoveryEntry]:
        """Merge discoveries, preserve feedback and return the bounded visible pool."""
        ...

    def read_feedback(self) -> list[DiscoveryEntry]:
        """Return explicit positive/negative signals without consuming them."""
        ...

    def mark_selected(self, entry: DiscoveryEntry) -> None:
        """Record successful Feed selection without changing feedback."""
        ...
