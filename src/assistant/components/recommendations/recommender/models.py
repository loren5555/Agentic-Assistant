"""Newspaper assessment and edition products.

Input origin:
    Discovery metadata, reading evidence and preference context.
Output destination:
    Ranked candidates, selection judgments and edition reports return to workflows.
Responsibility:
    Separate editorial conclusions, publication outcomes and optional source failures.
"""

from assistant.components.recommendations.discovery.models import DiscoveryResult, PaperCandidate
from assistant.components.recommendations.evidence_reader.models import PaperEvidence
from typing import Literal
from pydantic import BaseModel, Field
from assistant.runtime.records import ExecutionProcess


RecommendationCategory = Literal[
    "Understanding Daily", "Mainline Deep Read", "Frontier Radar", "Exceptional Event"
]


CATEGORIES: tuple[RecommendationCategory, ...] = (
    "Understanding Daily", "Mainline Deep Read", "Frontier Radar", "Exceptional Event"
)


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
    credibility: str = ""
    novelty: str = ""
    concerns: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    """Bundle a candidate with its accessible evidence and assessment."""

    candidate: PaperCandidate
    evidence: PaperEvidence
    assessment: RecommendationAssessment
    day: str = ""


class RecommendationRun(BaseModel):
    """Report selection separately from actual verified publication.

    Attributes:
        demo: Whether discovery is a fixture rather than a real search.
        discovery: Search candidates, coverage notes and invocation telemetry.
        evidence: Reading results, including rejected or unavailable candidates.
        failed_processes: CLI traces retained for failed provider invocations.
        selected: Candidates passing gates and daily maxima.
        rejected: Candidate identities and exclusion reasons.
        source_failures: Retrieval failures.
        published: Verified URLs, empty for demo runs.
        pending_recovery: Failed writes still awaiting retry.
    """

    demo: bool = False
    pool_count: int = 0
    discovery: DiscoveryResult | None = None
    evidence: dict[str, PaperEvidence] = Field(default_factory=dict)
    failed_processes: dict[str, ExecutionProcess] = Field(default_factory=dict)
    selected: list[Recommendation] = Field(default_factory=list)
    rejected: dict[str, str] = Field(default_factory=dict)
    source_failures: dict[str, str] = Field(default_factory=dict)
    published: list[str] = Field(default_factory=list)
    pending_recovery: dict[str, str] = Field(default_factory=dict)


class RankedCandidates(BaseModel):
    """Order pool source identities for selective reading; no publication yet."""

    ids: list[str]


class PoolTranslation(BaseModel):
    """Translate only display text while preserving bibliographic identity."""

    id: str
    display_title: str
    summary: str
    topics: list[str]
    discovery_reason: str


class PoolTranslations(BaseModel):
    """Return a batch of Chinese quick-skim presentations."""

    items: list[PoolTranslation]
