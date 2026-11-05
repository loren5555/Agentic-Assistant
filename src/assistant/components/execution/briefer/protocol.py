"""Approved reading capability.

Input origin:
    Available source material from the approved task.
Output destination:
    A grounded reading brief returns to the execution workflow.
Responsibility:
    Define briefing behavior without storage or workflow progression.
"""

from typing import Protocol
from assistant.components.execution.briefer.models import ReadingBrief, ReadingMaterial


class BriefWriterProtocol(Protocol):
    """Convert available source material into a grounded brief."""

    async def brief(self, capture: ReadingMaterial) -> ReadingBrief:
        """Classify and organize only the supplied material.

        Args:
            capture: Content and provenance available for reading.

        Returns:
            Organized output or a proposal classification.
        """
        ...
