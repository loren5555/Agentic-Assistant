"""Run articles: turn pending SimpRead captures into organized reading material.

Inputs:
    Optional explicit SimpRead page ID, including archived pages; otherwise up to
    the batch limit from the head of the Agent Archived = false collection.

Outputs:
    Confirmed Papers, Knowledge, or Workbench proposal URLs and local processing
    checkpoints. Successfully handled source pages receive Agent Archived = true.

Workflow:
    Delegate to shared steps/organize_capture with kind=simpread. Read content ->
    deduplicate -> brief -> publish or propose -> checkpoint -> acknowledge.
    Ordinary scans restart at the eligible queue head because archiving removes
    rows from the filtered collection. Explicit page checks do not move its cursor.

Participants and effects:
    SimpRead reader, briefing agent, organized-content publisher, and optionally
    proposal drafter and human approver. Called by run articles or a schedule.
    Reads/writes Notion and local state, but does not execute proposed further work.
"""

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
