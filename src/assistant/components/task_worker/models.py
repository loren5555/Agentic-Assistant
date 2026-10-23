"""Approved work and the deliverable returned by an executor."""

from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema

from assistant.components.proposer.models import Proposal
from assistant.runtime.records import ExecutionProcess


class TaskRequest(BaseModel):
    """Hand off an approved proposal or requested redo to an executor.

    Attributes:
        workbench_url: Proposal and review record.
        proposal: Approved scope, including its version.
        instruction: Human instructions supplementing this task.
        redo: Whether this task addresses an unqualified result.
    """

    workbench_url: str
    proposal: Proposal
    instruction: str
    redo: bool = False


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
