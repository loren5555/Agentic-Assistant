"""Human review and visible execution state on the workbench."""

from typing import Literal

from pydantic import BaseModel

from assistant.components.curator.models import CurationDecision
from assistant.components.proposer.models import Proposal
from assistant.components.task_worker.models import TaskResult


class WorkbenchItem(BaseModel):
    """Read a workbench row without coupling callers to Notion properties.

    Attributes:
        page_id: Workbench page identifier.
        url: Human-facing workbench link.
        title: Current proposal title.
        status: Proposal lifecycle state.
        human_review: Human approval decision.
        human_instruction: Human feedback for planning or execution.
        result_review: Human decision about the execution result.
        result_feedback: Human instructions for redoing the result.
        source_url: Link to original input.
        source_kind: Source database role, when managed by this workflow.
        proposal: Current structured proposal, or None for unmanaged records.
        result: Latest saved deliverable, if execution has completed.
        curation: Current extraction decision and verified destination links.
        publication_key: Report receipt stored in the Publication Key property.
        publication_applied: Whether the report has a publication receipt.
    """

    page_id: str
    url: str
    title: str
    status: str
    human_review: str
    human_instruction: str
    result_review: str
    result_feedback: str
    source_url: str
    source_kind: Literal["inbox", "todo", "notero", "simpread"] | None = None
    proposal: Proposal | None = None
    result: TaskResult | None = None
    curation: CurationDecision | None = None
    publication_key: str = ""
    publication_applied: bool = False
