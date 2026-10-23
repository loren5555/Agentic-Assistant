"""Run papers: organize raw Zotero-synced Notero entries for human reading.

Inputs:
    Optional Notero page ID; otherwise a bounded batch of new/changed captures
    selected using the saved cursor and locally handled page revisions.

Outputs:
    Confirmed organized-output or Workbench proposal URLs. Unchanged meaningful
    content is deduplicated rather than sent to the briefing agent again.

Workflow:
    Delegate to shared steps/organize_capture with kind=notero. That workflow
    reads evidence, obtains a brief, publishes an organized output or submits
    proposed further work, and checkpoints success before advancing the cursor.

Participants and effects:
    Notero reader, briefing agent, Papers publisher, and proposal/Workbench path
    when more work is required. Triggered by run papers or a configured schedule.
    Writes organized destinations and local state, never the raw Notero source.

Boundaries:
    Papers is output, not the raw library. An abstract-only brief is not a
    full-text reading; attachment metadata does not prove PDF acquisition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbos import DBOS

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows


@DBOS.workflow(name="organize_papers")
async def organize_papers(self: TaskWorkflows, page_id: str | None = None) -> list[str]:
    """Organize read-only Notero sources into Papers briefs or reviewed proposals.

    Args:
        self: Configured task runtime and shared capture steps.
        page_id: Optional explicit source; normal scans use a bounded saved cursor.

    Returns:
        Verified output links. Unchanged sources reuse their existing destinations.
    """
    # The shared capture workflow reads, briefs, publishes or proposes, then saves
    # its checkpoint. Only SimpRead inputs are marked handled; Notero is read-only.
    urls = await self.organize_captures("notero", page_id)
    return urls
