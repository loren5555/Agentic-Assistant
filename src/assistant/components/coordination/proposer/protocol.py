"""Capability interfaces for proposer."""

from typing import Protocol

from assistant.components.coordination.brainstorm.models import BrainstormContext, ExplorationReport
from assistant.components.coordination.proposer.assessment import ReportAssessment

from assistant.components.data.sources.models import SourceMaterial
from assistant.components.coordination.proposer.models import Proposal


class ProposerProtocol(Protocol):
    """Draft from one effective snapshot containing any prior review feedback."""

    async def draft(self, source: SourceMaterial) -> Proposal:
        """Draft one proposal without changing external storage.

        Args:
            source: Original material to organize into a proposal.

        Returns:
            The grounded proposal with its source fingerprint and version.
        """
        ...

    async def assess_report(self, context: BrainstormContext, report: ExplorationReport) -> ReportAssessment:
        """Read the whole report once and draft separately reviewable decisions."""
        ...
