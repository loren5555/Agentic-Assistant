"""Submit Notero papers through independent extraction and shared intake.

Input origin:
    The notero processor reads pending source records or an explicit page.
Output destination:
    Grounded source briefs go to Papers or Knowledge. Follow-up work goes to Workbench.
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
        Workbench links for follow-ups, archive links for reading-only inputs.
    """
    return await self.intake_sources(["notero"], page_id)
