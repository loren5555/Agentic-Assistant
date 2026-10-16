"""Replaceable discovery, reading, assessment, and feed capabilities."""

from typing import Protocol

from assistant.schemas.recommendation import (
    PaperCandidate, PaperEvidence, Recommendation, RecommendationAssessment, ResearchInterest,
)


class DiscoveryProtocol(Protocol):
    """Discover candidates without making claims about their quality."""

    def discover(self, interests: list[ResearchInterest]) -> list[PaperCandidate]:
        """Find candidates for the supplied interests.

        Args:
            interests: Read-only human-maintained research priorities.

        Returns:
            Candidate metadata requiring evidence assessment.
        """
        ...


class EvidenceReaderProtocol(Protocol):
    """Retrieve primary material independently from recommendation decisions."""

    def read(self, candidate: PaperCandidate) -> PaperEvidence:
        """Read available primary text.

        Args:
            candidate: Source to retrieve.

        Returns:
            Actual retrieved content and completeness information.
        """
        ...


class RecommenderProtocol(Protocol):
    """Assess evidence without publishing or modifying interests."""

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


class ResearchFeedProtocol(Protocol):
    """Read research priorities and publish verified real recommendations."""

    def initialize_schema(self) -> None:
        """Explicitly prepare stable identities for recommendation follow-ups."""
        ...

    def read_active_interests(self) -> list[ResearchInterest]:
        """Return active priorities without changing human-maintained fields."""
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

    def list_interested(self) -> list[dict[str, str]]:
        """Return Interested feed identities for Inbox follow-up dispatch."""
        ...

    def create_follow_up(self, feed_page_id: str) -> str:
        """Publish one Inbox follow-up without touching Papers.

        Args:
            feed_page_id: Feed identity reviewed as Interested.

        Returns:
            Verified Inbox URL or an empty string for withdrawn interest.
        """
        ...
