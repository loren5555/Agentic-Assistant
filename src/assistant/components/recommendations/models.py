"""Evidence-grounded discovery inputs and recommendation reports."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from assistant.runtime.records import ExecutionProcess

Breadth = Literal["Core", "Broader", "Neighboring", "Cross-disciplinary"]
BREADTHS = ("Core", "Broader", "Neighboring", "Cross-disciplinary")

RecommendationCategory = Literal[
    "Understanding Daily", "Mainline Deep Read", "Frontier Radar", "Exceptional Event"
]
CATEGORIES: tuple[RecommendationCategory, ...] = (
    "Understanding Daily", "Mainline Deep Read", "Frontier Radar", "Exceptional Event"
)


class ResearchInterest(BaseModel):
    """Describe a newspaper topic or explicit reading preference with its weight."""

    id: str
    title: str
    description: str = ""
    priority: float = 1.0


class SourceQuality(BaseModel):
    """Record verified publication context and substantive quality signals.

    Attributes:
        venue: Exact publication venue, or empty when not established.
        status: Verified publication stage, distinct from a claimed target venue.
        rank: Verified system/year/category label; empty when unverified.
        authors: Author names as found on the primary source.
        author_context: Relevant prior contributions with a stated evidence basis.
        novelty: Concrete contribution rather than a performance slogan.
        limitations: Unresolved checks and methodological concerns.
        sources: Pages supporting publication, ranking and author context.
    """

    model_config = ConfigDict(extra="forbid")
    venue: str = ""
    status: Literal["Published", "Accepted", "Preprint", "Unknown"] = "Unknown"
    rank: str = ""
    authors: list[str] = Field(default_factory=list)
    author_context: str = ""
    novelty: str = ""
    limitations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class PaperCandidate(BaseModel):
    """Identify discovered material without implying it has been read.

    Attributes:
        id: Provider identity used for deduplication.
        title: Source title.
        url: Primary source link.
        doi: DOI when available.
        demo: Whether the source is synthetic and prohibited from publication.
        published_date: Verified source publication date, or empty when unknown.
        discovery_reason: Search relevance lead, requiring evidence assessment.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    url: str
    doi: str = ""
    demo: bool = False
    published_date: str = ""
    discovery_reason: str = ""
    kind: Literal["Paper", "Finding", "Method", "Tool", "Dataset", "Other"] = "Paper"
    breadth: Breadth = "Core"
    summary: str = ""
    display_title: str = ""
    quality: SourceQuality = Field(default_factory=SourceQuality)
    topics: list[str] = Field(default_factory=list)


class DiscoveryResult(BaseModel):
    """Checkpoint searched candidates, search limitations and provider telemetry.

    Attributes:
        candidates: Bounded bibliographic candidates awaiting evidence review.
        notes: Search coverage, inaccessible sources and other limitations.
        process: Actual CLI events and usage, attached after model execution.
    """

    model_config = ConfigDict(extra="forbid")

    candidates: list[PaperCandidate]
    notes: list[str]
    process: SkipJsonSchema[ExecutionProcess | None] = None


class PaperEvidence(BaseModel):
    """Preserve exactly what was accessible to the recommendation agent.

    Attributes:
        primary_source: Whether the supplied content came from a primary source.
        full_text: Whether complete text was actually retrieved.
        text: Readable source material, not a model-generated substitute.
        source_url: Location of that material.
        failure: Retrieval failure or incompleteness explanation.
        reading_scope: Actual accessible material, such as abstract or excerpts.
        summary: Reader-generated synopsis, kept separate from source excerpts.
        limitations: Missing sections and unsupported claims the reader identified.
        process: Provider events and usage, attached after execution.
    """

    model_config = ConfigDict(extra="forbid")

    primary_source: bool
    full_text: bool
    text: str
    source_url: str
    failure: str = ""
    quality: SourceQuality = Field(default_factory=SourceQuality)
    reading_scope: str = "partial text"
    summary: str = ""
    limitations: list[str] = Field(default_factory=list)
    process: SkipJsonSchema[ExecutionProcess | None] = None


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
