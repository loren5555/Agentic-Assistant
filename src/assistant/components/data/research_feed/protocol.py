"""Selected edition storage interface.

Input origin:
    Recommender selections and optional human reading feedback.
Output destination:
    Verified Feed links and preference context return to workflows.
Responsibility:
    Own persistence and source lookup independently of editorial judgment.
"""

from typing import Protocol
from assistant.components.recommendations.discovery.models import DiscoveryResult, PaperCandidate, ResearchInterest
from assistant.components.recommendations.evidence_reader.models import PaperEvidence
from assistant.components.recommendations.recommender.models import Recommendation, RecommendationAssessment


class ResearchFeedProtocol(Protocol):
    """Read optional newspaper preferences and publish verified recommendations."""

    def initialize_schema(self) -> None:
        """Explicitly prepare stable recommendation publication identities."""
        ...

    def read_active_interests(self) -> list[ResearchInterest]:
        """Return active priorities without changing human-maintained fields."""
        ...

    def read_interested_papers(self) -> list[ResearchInterest]:
        """Return liked papers as preference context, without consuming their signals.

        Returns:
            Human-selected reading preferences, not candidate evaluation evidence.
        """
        ...

    def read_interested_feed(self) -> list[ResearchInterest]:
        """Read optional likes as preferences, without proposal intake."""
        ...

    def find_existing(self, candidate: PaperCandidate) -> str | None:
        """Find historical feed entries by source identity.

        Args:
            candidate: Candidate metadata and optional DOI.

        Returns:
            Existing feed URL or None.
        """
        ...

    def publish(self, recommendation: Recommendation, key: str) -> str:
        """Publish or recover one recommendation under a stable key.

        Args:
            recommendation: Qualified real source and its supporting report.
            key: Stable publication identifier supplied by the workflow.

        Returns:
            Verified destination URL.
        """
        ...
