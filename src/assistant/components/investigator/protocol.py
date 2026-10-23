"""Capability interfaces for investigator."""

from typing import Protocol

from assistant.components.investigator.models import InvestigationReport, InvestigationRequest


class InvestigatorProtocol(Protocol):
    """Investigate supplied material without changing external records."""

    async def investigate(self, request: InvestigationRequest) -> InvestigationReport:
        """Answer a question and identify supporting evidence.

        Args:
            request: Original question material and recalled context.

        Returns:
            An attributed answer with unresolved information made explicit.
        """
        ...
