"""Submit Notero papers through independent extraction and shared intake.

Input origin:
    The notero processor reads pending source records or an explicit page.
Output destination:
    Organizer and Proposer publish a Workbench proposal. Final reading or knowledge
    outputs are created only after execution and result acceptance.
Responsibility:
    Keep this source workflow independently extensible without copying intake logic.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from dbos import DBOS
from logger import trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows


@DBOS.workflow(name="JobWorkflows.organize_papers.v2")
@trace_call("workflow", "organize_papers")
async def organize_papers(self: TaskWorkflows, page_id: str | None = None) -> list[str]:
    """Prepare proposals from pending Notero papers.

    Args:
        page_id: Optional source page; does not bypass deduplication.

    Returns:
        Verified Workbench links.
    """
    return await self.intake_sources(["notero"], page_id)
