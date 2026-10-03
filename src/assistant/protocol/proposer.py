"""The independent capability responsible for managing proposals."""

from typing import Protocol

from assistant.schemas.proposal import ProposalCycle


class ProposerProtocol(Protocol):
    """Manage intake, resubmissions, and human review in one cycle."""

    async def run_cycle(self) -> ProposalCycle:
        """Process source material and review decisions.

        Returns:
            Changed proposal links and approved tasks awaiting execution.
        """
        ...
