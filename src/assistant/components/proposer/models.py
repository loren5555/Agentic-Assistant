"""The reviewable scope and expected result of proposed work."""

from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema

from assistant.runtime.records import ExecutionProcess


class Proposal(BaseModel):
    """Explain a proposed task in a report suitable for human review.

    Attributes:
        title: Short proposal title.
        understanding: Interpretation of the supplied material.
        purpose: Intended goal of the proposed work.
        reason: Why this work is useful or necessary.
        action: Concrete operation proposed for approval.
        plan: Steps within the proposed scope.
        expected_result: Deliverable and criteria for judging it.
        source_fingerprint: Content digest assigned by the provider.
        version: Proposal revision assigned by the provider.
        process: Actual drafting telemetry, excluded from model output schemas.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    understanding: str
    purpose: str
    reason: str
    action: str
    plan: list[str]
    expected_result: str
    source_fingerprint: SkipJsonSchema[str] = ""
    version: SkipJsonSchema[int] = 1
    process: SkipJsonSchema[ExecutionProcess | None] = None
