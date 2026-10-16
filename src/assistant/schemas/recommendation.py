"""Evidence-grounded discovery inputs and recommendation reports."""

from typing import Literal

from pydantic import BaseModel, Field


RecommendationCategory = Literal[
    "Understanding Daily", "Mainline Deep Read", "Frontier Radar", "Exceptional Event"
]
CATEGORIES: tuple[RecommendationCategory, ...] = (
    "Understanding Daily", "Mainline Deep Read", "Frontier Radar", "Exceptional Event"
)


class ResearchInterest(BaseModel):
    """Describe an existing human-maintained research interest."""

    id: str
    title: str
    description: str = ""


class PaperCandidate(BaseModel):
    """Identify discovered material without implying it has been read.

    Attributes:
        id: Provider identity used for deduplication.
        title: Source title.
        url: Primary source link.
        doi: DOI when available.
        demo: Whether the source is synthetic and prohibited from publication.
    """

    id: str
    title: str
    url: str
    doi: str = ""
    demo: bool = False


class PaperEvidence(BaseModel):
    """Preserve exactly what was accessible to the recommendation agent.

    Attributes:
        primary_source: Whether the supplied content came from a primary source.
        full_text: Whether complete text was actually retrieved.
        text: Readable source material, not a model-generated substitute.
        source_url: Location of that material.
        failure: Retrieval failure or incompleteness explanation.
    """

    primary_source: bool
    full_text: bool
    text: str
    source_url: str
    failure: str = ""


class RecommendationAssessment(BaseModel):
    """Explain a recommendation with separate epistemic layers.

    Attributes:
        qualified: Whether the evidence and relevance justify publication.
        category: Destination category, or None when rejected.
        reason: Grounded relevance or rejection explanation.
        author_claims: Claims attributed to the source authors.
        experimental_support: Experiments actually described in the evidence.
        agent_inference: Agent interpretation, clearly distinct from evidence.
    """

    qualified: bool
    category: RecommendationCategory | None
    reason: str
    author_claims: list[str]
    experimental_support: list[str]
    agent_inference: list[str]


class Recommendation(BaseModel):
    """Bundle a candidate with its accessible evidence and assessment."""

    candidate: PaperCandidate
    evidence: PaperEvidence
    assessment: RecommendationAssessment


class RecommendationRun(BaseModel):
    """Report selection separately from actual verified publication.

    Attributes:
        demo: Whether discovery is a fixture rather than a real search.
        selected: Candidates passing gates and daily maxima.
        rejected: Candidate identities and exclusion reasons.
        source_failures: Retrieval failures.
        published: Verified URLs, empty for demo runs.
        pending_recovery: Failed writes still awaiting retry.
    """

    demo: bool = False
    selected: list[Recommendation] = Field(default_factory=list)
    rejected: dict[str, str] = Field(default_factory=dict)
    source_failures: dict[str, str] = Field(default_factory=dict)
    published: list[str] = Field(default_factory=list)
    pending_recovery: dict[str, str] = Field(default_factory=dict)
