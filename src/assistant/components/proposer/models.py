"""The reviewable scope and expected result of proposed work."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from assistant.runtime.records import ExecutionProcess


class Proposal(BaseModel):
    """Explain a proposed task in a report suitable for human review.

    Attributes:
        title: Short proposal title.
        kind: Whether the next participant is an executor or the human.
        understanding: Interpretation of the supplied material.
        purpose: Intended goal of the proposed work.
        reason: Why this work is useful or necessary.
        action: Concrete operation proposed for approval.
        plan: Steps within the proposed scope.
        expected_result: Deliverable and criteria for judging it.
        questions: Essential user-owned information requested before planning.
        source_fingerprint: Content digest assigned by the provider.
        version: Proposal revision assigned by the provider.
        process: Actual drafting telemetry, excluded from model output schemas.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    kind: Literal["execution", "clarification"] = "execution"
    understanding: str
    reason: str
    purpose: str = ""
    action: str = ""
    plan: list[str] = Field(default_factory=list)
    expected_result: str = ""
    questions: list[str] = Field(default_factory=list)
    source_fingerprint: SkipJsonSchema[str] = ""
    version: SkipJsonSchema[int] = 1
    process: SkipJsonSchema[ExecutionProcess | None] = None

    @model_validator(mode="after")
    def check_next_action(self) -> "Proposal":
        """Require questions for human input and concrete scope for execution.

        Returns:
            A proposal whose content supports the selected next participant.
        """
        if self.kind == "clarification":
            if not self.questions or any(not question.strip() for question in self.questions):
                raise ValueError("A clarification proposal requires focused questions")
        elif (
            not all(value.strip() for value in (self.purpose, self.action, self.expected_result))
            or not self.plan
        ):
            raise ValueError("An execution proposal requires a purpose, action, plan and expected result")
        return self
