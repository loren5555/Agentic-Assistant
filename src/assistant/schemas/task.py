"""Current results of approved work, without a separate task database."""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from assistant.schemas.process import ExecutionProcess


class TaskResult(BaseModel):
    """Present the deliverable produced for an approved proposal.

    Attributes:
        content: Completed answer or report in Markdown.
        action_id: Capability selected by the execution router.
        process: Runtime telemetry, not model-generated content.
    """

    model_config = ConfigDict(extra="forbid")

    content: str
    action_id: SkipJsonSchema[str] = ""
    process: SkipJsonSchema[ExecutionProcess | None] = None


class ExecutionCycle(BaseModel):
    """Summarize the current execution pass.

    Attributes:
        executed: Pages with saved results awaiting human acceptance.
        needs_input: Pages returned for human clarification.
        failed: Page links and the actual errors encountered.
    """

    executed: list[str] = Field(default_factory=list)
    needs_input: list[str] = Field(default_factory=list)
    failed: dict[str, str] = Field(default_factory=dict)
