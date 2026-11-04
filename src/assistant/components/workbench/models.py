"""Human review and visible execution state on the workbench."""

import hashlib
import json

from pydantic import BaseModel

from assistant.components.curator.models import CurationDecision
from assistant.components.proposer.models import Proposal
from assistant.components.task_worker.models import TaskResult
from assistant.components.inputs.models import SourceKind


def result_publication_key(version: int, content: str) -> str:
    """Identify a result within a proposal version.

    Args:
        version: Approved proposal version.
        content: Published result text.

    Returns:
        Stable publication receipt.
    """
    payload = json.dumps([version, content], ensure_ascii=False)
    return "result:" + hashlib.sha256(payload.encode()).hexdigest()


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
        proposal_version: Revision displayed in the Workbench number property.
        execution_error: Latest human-visible execution failure, cleared on success.
        selected_action_id: Live storage property identifying the reviewed capability.
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
    source_kind: SourceKind | None = None
    proposal: Proposal | None = None
    result: TaskResult | None = None
    curation: CurationDecision | None = None
    publication_key: str = ""
    publication_applied: bool = False
    proposal_version: int | None = None
    execution_error: str = ""
    selected_action_id: str = ""

    @property
    def needs_input(self) -> bool:
        """Identify a human-input turn from its waiting state or proposal kind.

        Returns:
            Whether an answer should return to the source before execution.
        """
        return self.status == "Needs Input" or (
            self.proposal is not None and self.proposal.kind == "clarification"
        )
