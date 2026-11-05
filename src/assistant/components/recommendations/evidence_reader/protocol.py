"""Evidence reading interface.

Input origin:
    A candidate selected for closer inspection.
Output destination:
    Accessible primary material and limitations return to Recommender.
Responsibility:
    Define reading without source selection or Feed persistence.
"""

from typing import Protocol
from assistant.components.recommendations.discovery.models import PaperCandidate
from assistant.components.recommendations.evidence_reader.models import PaperEvidence


class EvidenceReaderProtocol(Protocol):
    """Retrieve primary material independently from recommendation decisions."""

    async def read(self, candidate: PaperCandidate) -> PaperEvidence:
        """Read available primary text.

        Args:
            candidate: Source to retrieve.

        Returns:
            Actual retrieved content and completeness information.
        """
        ...
