"""Primary reading evidence.

Input origin:
    A shortlisted discovery and the source pages actually accessed.
Output destination:
    Recommender receives original excerpts, reading scope and source-quality context.
Responsibility:
    Keep source material separate from reader-generated synopsis and inference.
"""

from assistant.components.recommendations.discovery.models import SourceQuality
from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema
from assistant.runtime.records import ExecutionProcess


class ReviewDiscussion(BaseModel):
    """Preserve one public note's role, raw scale, thread and source link."""
    model_config = ConfigDict(extra="forbid")
    id: str
    role: str
    reply_to: str = ""
    url: str
    modified: str = ""
    content: dict[str, str] = Field(default_factory=dict)


class PaperFigure(BaseModel):
    """A representative illustration observed on the primary publication."""

    model_config = ConfigDict(extra="forbid")
    image_url: str
    source_url: str
    caption: str


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
    figure: PaperFigure | None = None
    limitations: list[str] = Field(default_factory=list)
    process: SkipJsonSchema[ExecutionProcess | None] = None
    discussions: SkipJsonSchema[list[ReviewDiscussion]] = Field(default_factory=list)
    discussion_limitations: list[str] = Field(default_factory=list)
