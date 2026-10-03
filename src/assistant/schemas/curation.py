"""Useful outcomes retained after human acceptance, not workflow history."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema


class RetainedArtifact(BaseModel):
    """Describe a reusable outcome grounded in an accepted result.

    Attributes:
        kind: Long-term destination for knowledge or a research idea.
        title: Concise title for retrieval.
        content: Standalone Markdown retaining evidence and uncertainty.
        reason: Value beyond this particular task.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["knowledge", "idea"]
    title: str
    content: str
    reason: str


class ArchiveReceipt(BaseModel):
    """Identify a verified retained outcome.

    Attributes:
        key: Stable publication key shared across retries.
        url: Destination page link.
    """

    key: str
    url: str


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
    receipts: SkipJsonSchema[list[ArchiveReceipt]] = Field(default_factory=list)


class CurationCycle(BaseModel):
    """Summarize finalization without a growing activity history.

    Attributes:
        finished: Accepted tasks without a long-term outcome.
        archived: Accepted tasks with verified retained outcomes.
        failed: Source links and errors; these tasks remain Executed.
    """

    finished: list[str] = Field(default_factory=list)
    archived: list[str] = Field(default_factory=list)
    failed: dict[str, str] = Field(default_factory=dict)
