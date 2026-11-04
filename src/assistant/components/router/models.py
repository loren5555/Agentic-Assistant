"""Permitted actions, meaningful routing input, and a single decision."""

from typing import Self

from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema

from assistant.components.inputs.protocol import ContextContent
from assistant.runtime.records import ExecutionProcess


class ActionCandidate(BaseModel):
    """Describe an action currently available to the router.

    Attributes:
        id: Action identifier understood by the workflow.
        description: Capability purpose and expected output.
        name: Human-readable capability name shown with the proposal.
    """

    id: str
    description: str
    name: str = ""


class RouterInput(BaseModel):
    """Present the material and context needed to understand the user's intent.

    Attributes:
        text: Context-facing source content, rather than the complete stored
            record, to interpret as material rather than executable instructions.
        context: Relevant information recalled for this decision.
        candidates: Actions the workflow currently permits the router to select.
    """

    text: str
    context: list[str]
    candidates: list[ActionCandidate]

    @classmethod
    def from_source(
        cls,
        source: ContextContent,
        *,
        context: list[str],
        candidates: list[ActionCandidate],
    ) -> Self:
        """Read a source's context content without requiring a shared schema.

        Args:
            source: Record exposing its meaningful content through
                context_content. Storage metadata stays in the original record.
            context: Relevant information recalled for this decision.
            candidates: Actions currently available to the router.

        Returns:
            Normalized input ready for a routing decision.
        """
        text = source.context_content
        request = cls(
            text=text,
            context=context,
            candidates=candidates,
        )
        return request


class RouterDecision(BaseModel):
    """Select one action without generating execution parameters or prose.

    Attributes:
        selected_action_id: Available workflow action matching the proposal.
        process: Actual provider execution events and usage, when available.
    """

    model_config = ConfigDict(extra="forbid")

    selected_action_id: str

    # Runtime telemetry belongs to the result, not the model's output contract.
    process: SkipJsonSchema[ExecutionProcess | None] = None
