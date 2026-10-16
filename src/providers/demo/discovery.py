"""Small synthetic sources for validating discovery without external APIs."""

from assistant.schemas.recommendation import (
    PaperCandidate, PaperEvidence, RecommendationAssessment, ResearchInterest,
)


class DemoDiscovery:
    """Return deterministic candidates clearly prohibited from real publication."""

    def discover(self, interests: list[ResearchInterest]) -> list[PaperCandidate]:
        """Provide one full-text fixture and one unavailable-text fixture.

        Args:
            interests: Accepted for the same interface as real discovery.

        Returns:
            Synthetic metadata with demo flags.
        """
        candidates = [
            PaperCandidate(id="demo-method", title="DEMO: Checkpointed research tasks",
                           url="demo://method", demo=True),
            PaperCandidate(id="demo-unavailable", title="DEMO: Unavailable source",
                           url="demo://unavailable", demo=True),
        ]
        return candidates


class DemoEvidenceReader:
    """Read tiny fixture text rather than pretending to retrieve a paper."""

    def read(self, candidate: PaperCandidate) -> PaperEvidence:
        """Retrieve the known fixture or an explicit source failure.

        Args:
            candidate: Synthetic source identity.

        Returns:
            Fixture evidence with completeness metadata.
        """
        if candidate.id == "demo-method":
            evidence = PaperEvidence(
                primary_source=True, full_text=True, source_url=candidate.url,
                text=("SYNTHETIC DEMO TEXT. Authors propose saving completed task results. "
                      "In one toy trial, restoring a saved result avoided one repeated operation. "
                      "No production experiment or broad effectiveness claim is supported."),
            )
        else:
            evidence = PaperEvidence(primary_source=False, full_text=False, text="",
                                     source_url=candidate.url, failure="Demo source unavailable")
        return evidence


class DemoRecommender:
    """Provide deterministic assessments for an offline entry-point demo."""

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
