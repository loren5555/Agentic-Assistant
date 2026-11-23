"""Reusable outcomes extracted from human-accepted work."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from assistant.components.data.publisher.models import PublicationReceipt
from assistant.components.execution.briefer.models import PaperReadingMetadata


class RetainedArtifact(BaseModel):
    """Describe a reusable outcome grounded in an accepted result.

    Attributes:
        kind: Long-term destination for knowledge or a research idea.
        title: Concise title for retrieval.
        content: Scope and evidence for a writing commission, or the reviewed manuscript.
        reason: Value beyond this particular task.
        target_idea_page_id: Existing project receiving an appended finding.
        reading: Paper reading properties supported by the accepted result.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["spark", "knowledge", "idea", "paper", "research_interest"]
    title: str
    content: str
    reason: str
    reading: PaperReadingMetadata | None = None
    target_page_id: str | None = Field(default=None, exclude_if=lambda v: v is None,
        description="Existing verified Papers or Knowledge page for the same work.")
    contribution: Literal["work", "discussion", "addition"] = Field(default="work", exclude_if=lambda v: v == "work")
    target_revision: SkipJsonSchema[str] = Field(default="", exclude_if=lambda v: not v)
    summary: SkipJsonSchema[str] = Field(default="", exclude_if=lambda v: not v)
    evidence_level: SkipJsonSchema[str | None] = Field(default=None, exclude_if=lambda v: v is None)
    target_idea_page_id: str | None = Field(default=None, exclude_if=lambda value: value is None, description="Existing Idea receiving this finding, or null for a new entry.")

    @model_validator(mode="after")
    def validate_destination(self) -> "RetainedArtifact":
        if getattr(self, "target_idea_page_id", None) is not None:
            if self.kind != "idea" or not self.target_idea_page_id.strip():
                raise ValueError("Only a finding for an existing Idea can name a target page")
        if self.target_page_id and self.kind not in {"knowledge", "paper"}:
            raise ValueError("A manuscript page target must belong to Knowledge or Papers")
        if self.contribution == "discussion" and self.kind != "paper":
            raise ValueError("A paper discussion requires a paper destination")
        return self


class CurationDecision(BaseModel):
    """Keep one current extraction decision and its publication progress.

    Attributes:
        reason: Why useful outcomes are retained, or none are retained.
        artifacts: Reusable material supported by the accepted result.
        result_fingerprint: Provider-assigned digest of the accepted result and scope.
        receipts: Verified destination writes, not model-generated content.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str
    artifacts: list[RetainedArtifact]
    result_fingerprint: SkipJsonSchema[str] = ""
    receipts: SkipJsonSchema[list[PublicationReceipt]] = Field(default_factory=list)
