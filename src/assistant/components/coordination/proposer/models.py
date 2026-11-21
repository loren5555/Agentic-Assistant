"""The reviewable scope and expected result of proposed work."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from assistant.components.coordination.curator.models import RetainedArtifact
from assistant.runtime.records import ExecutionProcess
from assistant.components.coordination.router.models import ActionCandidate
from assistant.components.execution.planner.models import ExecutionPlan


class Proposal(BaseModel):
    """A human-reviewable task, clarification, or retention proposal.

    The proposal describes the user's goal, supporting material, planned action
    and expected result. Clarifications ask focused questions. Retention proposals
    identify material and its destination. The runtime attaches routing, accepted
    plans, versions and execution telemetry before publishing to Workbench.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    kind: Literal["execution", "clarification", "retention"] = "execution"
    retention: RetainedArtifact | None = Field(default=None, exclude_if=lambda value: value is None)
    understanding: str
    reason: str
    purpose: str = ""
    action: str = ""
    plan: list[str] = Field(default_factory=list)
    expected_result: str = ""
    questions: list[str] = Field(default_factory=list)
    selected_action: SkipJsonSchema[ActionCandidate | None] = None
    execution_plan: SkipJsonSchema[ExecutionPlan | None] = None
    routing_process: SkipJsonSchema[ExecutionProcess | None] = None
    source_fingerprint: SkipJsonSchema[str] = ""
    version: SkipJsonSchema[int] = 1
    process: SkipJsonSchema[ExecutionProcess | None] = None

    @model_validator(mode="after")
    def check_next_action(self) -> "Proposal":
        """Require questions for human input and concrete scope for execution.

        Returns:
            A proposal whose content supports the selected next participant.
        """
        if self.kind == "retention":
            if self.retention is None or self.retention.kind not in {"spark", "idea"}:
                raise ValueError("A retention proposal must specify its Spark or Idea")
            if not all(part.strip() for part in (self.retention.title, self.retention.content, self.retention.reason)):
                raise ValueError("Retention requires a title, material, and reason for review")
            return self
        if getattr(self, "retention", None) is not None:
            raise ValueError("Only retention proposals carry material ready for publication")
        if self.kind == "clarification":
            if not self.questions or any(not question.strip() for question in self.questions):
                raise ValueError("A clarification proposal requires focused questions")
        elif (
            not all(value.strip() for value in (self.purpose, self.action, self.expected_result))
            or not self.plan
        ):
            raise ValueError("An execution proposal requires a purpose, action, plan and expected result")
        return self
