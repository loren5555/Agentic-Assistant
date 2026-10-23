"""Capability interfaces for workbench."""

from typing import Protocol

from assistant.components.curator.models import CurationDecision
from assistant.components.inputs.models import SourceMaterial
from assistant.components.proposer.models import Proposal
from assistant.components.task_worker.models import TaskResult
from assistant.components.workbench.models import WorkbenchItem


class WorkbenchProtocol(Protocol):
    """Maintain proposal reports, results, and human review states."""

    def initialize_schema(self) -> None:
        """Explicitly prepare the storage additions required by this capability."""
        ...

    def list_items(self, statuses: list[str]) -> list[WorkbenchItem]:
        """Read proposals in the requested lifecycle states.

        Args:
            statuses: Workbench states included in the storage query.

        Returns:
            Matching workbench rows and their report content.
        """
        ...

    def read_item(self, page_id: str) -> WorkbenchItem:
        """Read current human feedback before acting.

        Args:
            page_id: Workbench page identifier.

        Returns:
            Current proposal and human decisions.
        """
        ...

    def submit(self, source: SourceMaterial, proposal: Proposal, workflow_id: str = "") -> WorkbenchItem:
        """Submit a proposal for human review.

        Args:
            source: Original material.
            proposal: Report to submit.
            workflow_id: Stable publication identity for recovering lost acknowledgements.

        Returns:
            Created workbench row.
        """
        ...

    def revise(self, item: WorkbenchItem, proposal: Proposal) -> WorkbenchItem:
        """Replace the current proposal and request a fresh approval.

        Args:
            item: Existing proposal row.
            proposal: Revised report.

        Returns:
            Updated workbench row.
        """
        ...

    def set_status(self, item: WorkbenchItem, status: str) -> None:
        """Update proposal lifecycle status.

        Args:
            item: Workbench row to update.
            status: New lifecycle state.
        """
        ...

    def save_result(self, item: WorkbenchItem, result: TaskResult) -> None:
        """Save the current deliverable and request human acceptance.

        Args:
            item: Workbench proposal whose approved version was executed.
            result: Actual completed output.
        """
        ...

    def request_input(self, item: WorkbenchItem, question: str) -> None:
        """Return a blocked proposal to human review without claiming execution.

        Args:
            item: Proposal requiring a user-owned choice or missing material.
            question: Focused question displayed on the proposal page.
        """
        ...

    def save_error(self, item: WorkbenchItem, error: str) -> None:
        """Record an execution failure without marking the task Executed.

        Args:
            item: Proposal whose execution failed.
            error: Original failure description.
        """
        ...

    def save_curation(self, item: WorkbenchItem, decision: CurationDecision) -> None:
        """Save the current extraction and verified destination links.

        Args:
            item: Human-accepted task being finalized.
            decision: Current decision checkpoint, not a history entry.
        """
        ...
