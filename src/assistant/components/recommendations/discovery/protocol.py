"""Public discovery interface.

Input origin:
    Newspaper preferences and an intended search date.
Output destination:
    Candidate metadata returns to the recommendation workflow and discovery cache.
Responsibility:
    Search independently of evidence assessment and publication.
"""

from typing import Protocol
from assistant.components.recommendations.discovery.models import DiscoveryResult, ResearchInterest


class DiscoveryProtocol(Protocol):
    """Discover candidates without making claims about their quality."""

    async def discover(self, interests: list[ResearchInterest], day: str) -> DiscoveryResult:
        """Find candidates for the supplied interests.

        Args:
            interests: Read-only human-maintained research priorities.
            day: Intended recommendation date in ISO format.

        Returns:
            Candidate metadata requiring evidence assessment.
        """
        ...
