"""Contracts shared by weekly exploration and daily source collection."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from assistant.components.recommendations.discovery.models import (
    DiscoveryResult,
    PaperCandidate,
    ResearchInterest,
)

CollectionMode = Literal["deep", "light"]
AgeBucket = Literal[
    "week", "month", "quarter", "half_year", "year", "three_years", "older"
]


class SearchDirection(BaseModel):
    """A concrete reusable query allocated to a breadth and publication-age range."""

    model_config = ConfigDict(extra="forbid")
    query: str
    breadth: Literal["Core", "Broader", "Neighboring", "Cross-disciplinary"]
    age: AgeBucket
    reason: str = ""


class CoverageCell(BaseModel):
    """Show actual publication count and target share for one distribution cell."""

    model_config = ConfigDict(extra="forbid")
    breadth: str
    age: AgeBucket
    target: float
    published: int = 0
    deficit: float = 0
    available: int = 0


class CollectionRequest(BaseModel):
    """Give collectors a bounded brief, not the entire history or private credentials."""

    model_config = ConfigDict(extra="forbid")
    day: str
    mode: CollectionMode
    interests: list[ResearchInterest]
    coverage: list[CoverageCell]
    pool: list[PaperCandidate] = Field(default_factory=list)
    directions: list[SearchDirection] = Field(default_factory=list)
    max_queries: int = 6
    max_candidates: int = 40


class CollectionResult(BaseModel):
    """Retain discoveries, reusable queries and source-level retrieval failures."""

    model_config = ConfigDict(extra="forbid")
    mode: CollectionMode
    discovery: DiscoveryResult
    directions: list[SearchDirection]
    failures: dict[str, str] = Field(default_factory=dict)
