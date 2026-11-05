"""Provide offline editorial fixtures.

Input origin:
    Synthetic candidates, evidence and preference context.
Output destination:
    Deterministic rankings and assessments return to the demo workflow.
Responsibility:
    Verify the recommendation path without model or publication calls.
"""

from assistant.components.recommendations.discovery.models import PaperCandidate, ResearchInterest
from assistant.components.recommendations.evidence_reader.models import PaperEvidence
from assistant.components.recommendations.recommender.models import RecommendationAssessment
from logger import trace_call


class DemoRecommender:
    """Provide deterministic assessments for an offline entry-point demo."""

    @trace_call("component", "recommendations.assess")
    async def assess(self, candidate: PaperCandidate, evidence: PaperEvidence,
                     interests: list[ResearchInterest]) -> RecommendationAssessment:
        """Assess the fixture without consuming model quota.

        Args:
            candidate: Fixture metadata.
            evidence: Supplied fixture text.
            interests: Read-only priorities accepted for interface parity.

        Returns:
            Demonstration assessment that cannot be published as real research.
        """
        assessment = RecommendationAssessment(
            qualified=bool(evidence.text), category="Understanding Daily" if evidence.text else None,
            reason="Offline fixture validates the report path, not scientific quality.",
            author_claims=["Saving completed results can avoid repeating completed work."],
            experimental_support=["One synthetic toy trial avoided one repeated operation."],
            agent_inference=["This fixture does not establish production effectiveness."],
        )
        return assessment

    async def rank(self, candidates: list[PaperCandidate], interests: list[ResearchInterest]) -> list[str]:
        """Retain fixture order without real model usage."""
        return [candidate.id for candidate in candidates]


Recommender = DemoRecommender
