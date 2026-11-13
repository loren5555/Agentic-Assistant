"""Define collection independently of source transport and newspaper publishing."""

from typing import Protocol
from .models import CollectionRequest, CollectionResult


class CollectorProtocol(Protocol):
    """Acquire attributed candidates under the supplied search budget."""

    async def collect(self, request: CollectionRequest) -> CollectionResult:
        """Return discoveries and directions; the workflow persists them in Pool."""
        ...
