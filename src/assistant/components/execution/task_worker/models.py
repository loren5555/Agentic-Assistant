"""Approved work and the deliverable returned by an executor."""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from assistant.components.coordination.proposer.models import Proposal
from assistant.runtime.records import ExecutionProcess
from assistant.components.data.sources.models import SourceMaterial
from assistant.components.coordination.curator.models import RetainedArtifact
from assistant.components.execution.planner.models import ExecutionPlan


class TaskRequest(BaseModel):
    """Hand off one approved source snapshot to an executor.

    Attributes:
        workbench_url: Proposal and review record.
        proposal: Approved scope, including its version.
        instruction: Human instructions supplementing this task.
        source: Effective source snapshot, including feedback and history.
    """

    workbench_url: str
    proposal: Proposal
    instruction: str
    source: SourceMaterial


class TaskResult(BaseModel):
    """Present the deliverable produced for an approved proposal.

    Attributes:
        content: Completed answer or report in Markdown.
        action_id: Capability selected by the execution router.
        process: Runtime telemetry, not model-generated content.
        artifacts: Structured outputs proposed for retention after acceptance.
        plan: Concrete plan produced by the Planner for separate review.
        questions: Essential user-owned information needed to complete the task.
    """

    model_config = ConfigDict(extra="forbid")

    content: str
    artifacts: list[RetainedArtifact] = Field(default_factory=list)
    plan: ExecutionPlan | None = None
    questions: list[str] = Field(default_factory=list)
    action_id: SkipJsonSchema[str] = ""
    process: SkipJsonSchema[ExecutionProcess | None] = None
