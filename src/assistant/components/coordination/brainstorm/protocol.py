"""Read a bounded research context, then explore it once for the report reviewer."""

from collections.abc import Callable, Mapping
from typing import Protocol

from .models import BrainstormContext, BrainstormMode, ExplorationReport


VersionLookup = Callable[[list[str]], Mapping[str, str]]


class ResearchLibraryProtocol(Protocol):
    def context(
        self, mode: BrainstormMode, page_id: str | None = None, *,
        lookup_versions: VersionLookup | None = None,
    ) -> BrainstormContext | None:
        """Retrieve one eligible seed and relevant history, or indicate an empty queue."""
        ...


class BrainstormProtocol(Protocol):
    async def explore(self, context: BrainstormContext) -> ExplorationReport:
        """Combine internal findings with public evidence and propose candidate items."""
        ...
