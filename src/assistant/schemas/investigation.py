"""Questions delegated for investigation and their attributed answers."""

from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema

from assistant.schemas.process import ExecutionProcess


class InvestigationRequest(BaseModel):
    """Provide original question material and relevant recalled context.

    Attributes:
        question: Original input to answer, including its supplied material.
        context: Relevant information supporting this investigation.
    """

    question: str
    context: list[str]


class SourceEvidence(BaseModel):
    """Identify a public source and what it supports in the answer.

    Attributes:
        title: Human-readable source title.
        url: Direct public link to the supporting source.
        finding: Specific finding supported by this source.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    finding: str


class InvestigationReport(BaseModel):
    """Return an answer with evidence and unresolved information.

    Attributes:
        answer: User-facing answer with source links where appropriate.
        sources: Sources actually consulted and their supporting findings.
        limitations: Unknown facts, inaccessible sources, or remaining questions.
        process: Actual provider execution events and usage, when available.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str
    sources: list[SourceEvidence]
    limitations: list[str]

    # Runtime telemetry belongs to the result, not the model's output contract.
    process: SkipJsonSchema[ExecutionProcess | None] = None
