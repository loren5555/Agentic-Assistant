"""Provide offline discovery fixtures.

Input origin:
    The same preference/date contract as real discovery.
Output destination:
    Synthetic candidates return to the demo newspaper workflow.
Responsibility:
    Exercise the path without public search or Notion publication.
"""

from assistant.components.recommendations.discovery.models import DiscoveryResult, PaperCandidate, ResearchInterest
from logger import trace_call


class DemoDiscovery:
    """Return deterministic candidates clearly prohibited from real publication."""

    @trace_call("component", "recommendations.discover")
    async def discover(self, interests: list[ResearchInterest], day: str) -> DiscoveryResult:
        """Provide one full-text fixture and one unavailable-text fixture.

        Args:
            interests: Accepted for the same interface as real discovery.
            day: Intended recommendation date; fixtures are independent of date.

        Returns:
            Synthetic metadata with demo flags.
        """
        candidates = [
            PaperCandidate(id="demo-method", title="DEMO: Checkpointed research tasks",
                           url="demo://method", demo=True),
            PaperCandidate(id="demo-unavailable", title="DEMO: Unavailable source",
                           url="demo://unavailable", demo=True),
        ]
        return DiscoveryResult(candidates=candidates, notes=["Synthetic offline fixture"])


Discovery = DemoDiscovery
