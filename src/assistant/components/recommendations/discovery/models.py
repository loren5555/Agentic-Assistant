"""Public research discovery contracts.

Input origin:
    Initial topics, human preferences and public-source search.
Output destination:
    Discovery Pool receives canonical candidates, quality provenance and search notes.
Responsibility:
    Represent discovery leads without implying a complete reading or selected edition.
"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema
from assistant.runtime.records import ExecutionProcess


Breadth = Literal["Core", "Broader", "Neighboring", "Cross-disciplinary"]


BREADTHS = ("Core", "Broader", "Neighboring", "Cross-disciplinary")


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
