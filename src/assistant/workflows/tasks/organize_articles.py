"""Organize SimpRead articles and acknowledge only verified outputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbos import DBOS

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows


@DBOS.workflow(name="organize_articles")
async def organize_articles(self: TaskWorkflows, page_id: str | None = None) -> list[str]:
    """Organize SimpRead articles and acknowledge only verified outputs.

    Args:
        self: Configured task runtime and shared capture steps.
        page_id: Optional explicit source; normal scans use a bounded saved cursor.

    Returns:
        Verified output links. Unchanged sources reuse their existing destinations.
    """
    # The shared capture workflow reads, briefs, publishes or proposes, then saves
    # its checkpoint. Only SimpRead inputs are marked handled; Notero is read-only.
    urls = await self.organize_captures("simpread", page_id)
    return urls
