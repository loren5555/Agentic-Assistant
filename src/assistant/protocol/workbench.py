"""Storage operations needed by the proposal management capability."""

from typing import Protocol

from assistant.schemas.proposal import Proposal, SourceMaterial, WorkbenchItem
from assistant.schemas.task import TaskResult
from assistant.schemas.curation import CurationDecision


class WorkbenchProtocol(Protocol):
    """Read sources and maintain proposal reports and review states."""

    def list_inputs(self) -> list[SourceMaterial]:
        """Read unarchived Inbox and elevated TODO material.

        Returns:
            Materials awaiting intake.
        """
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

    def read_source(self, source_url: str) -> SourceMaterial:
        """Read original material regardless of its intake status.

        Args:
            source_url: Original input link.

        Returns:
            Current source material.
        """
        ...

    def submit(self, source: SourceMaterial, proposal: Proposal) -> WorkbenchItem:
        """Submit a proposal for human review.

        Args:
            source: Original material.
            proposal: Report to submit.

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

    def close_source(self, source: SourceMaterial) -> None:
        """Mark successfully submitted input as handled.

        Args:
            source: Inbox to archive or TODO to mark handled.
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
