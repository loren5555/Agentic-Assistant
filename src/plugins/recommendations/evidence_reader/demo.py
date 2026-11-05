"""Provide offline reading fixtures.

Input origin:
    A synthetic discovery identity.
Output destination:
    Fixture evidence or explicit unavailability returns to demo assessment.
Responsibility:
    Keep synthetic material excluded from production publication.
"""

from assistant.components.recommendations.discovery.models import PaperCandidate
from assistant.components.recommendations.evidence_reader.models import PaperEvidence
from logger import trace_call


class DemoEvidenceReader:
    """Read tiny fixture text rather than pretending to retrieve a paper."""

    @trace_call("component", "recommendations.read")
    async def read(self, candidate: PaperCandidate) -> PaperEvidence:
        """Retrieve the known fixture or an explicit source failure.

        Args:
            candidate: Synthetic source identity.

        Returns:
            Fixture evidence with completeness metadata.
        """
        if candidate.id == "demo-method":
            evidence = PaperEvidence(
                primary_source=True, full_text=True, reading_scope="full text", source_url=candidate.url,
                text=("SYNTHETIC DEMO TEXT. Authors propose saving completed task results. "
                      "In one toy trial, restoring a saved result avoided one repeated operation. "
                      "No production experiment or broad effectiveness claim is supported."),
            )
        else:
            evidence = PaperEvidence(primary_source=False, full_text=False, text="",
                                     source_url=candidate.url, failure="Demo source unavailable")
        return evidence


EvidenceReader = DemoEvidenceReader
