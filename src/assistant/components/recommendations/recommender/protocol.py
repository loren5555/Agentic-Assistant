"""Editorial ranking and assessment interface.

Input origin:
    Discovery Pool metadata and accessible evidence.
Output destination:
    Rankings and grounded judgments return to the newspaper workflow.
Responsibility:
    Judge selection without modifying source records or human preferences.
"""

from typing import Protocol
from assistant.components.recommendations.discovery.models import PaperCandidate, ResearchInterest
from assistant.components.recommendations.evidence_reader.models import PaperEvidence
from assistant.components.recommendations.recommender.models import RecommendationAssessment


class RecommenderProtocol(Protocol):
    """Assess evidence without publishing or modifying interests."""

    async def rank(self, candidates: list[PaperCandidate], interests: list[ResearchInterest]) -> list[str]:
        """Rank pool metadata before selective source reading."""
        ...

    async def assess(
        self, candidate: PaperCandidate, evidence: PaperEvidence,
        interests: list[ResearchInterest],
    ) -> RecommendationAssessment:
        """Judge source quality and relevance.

        Args:
            candidate: Source metadata.
            evidence: Retrieved primary material.
            interests: Current research priorities.

        Returns:
            Grounded assessment, including explicit rejection when appropriate.
        """
        ...
