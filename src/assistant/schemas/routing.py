"""Available actions and the information needed to select one."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict

from assistant.protocol.content import ContextContent

class Trigger(BaseModel):
    """Identify one invocation independently of its task content.

    Attributes:
        event_id: Identifier used to trace this invocation.
        origin: System or interface that produced the trigger.
        kind: How the workflow was started.
        event_type: Optional source-specific event label.
    """

    event_id: str
    origin: str
    kind: Literal["manual", "event", "scheduled"]
    event_type: str | None = None


class ActionCandidate(BaseModel):
    """Describe an action currently available to the router.

    Attributes:
        id: Action identifier understood by the workflow.
        description: Capability purpose and expected output.
    """

    id: str
    description: str


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
    """Describe the input's meaning and propose one next action.

    Attributes:
        content_types: Semantic labels such as note, question, idea, or request.
        user_intent: What the user appears to want from the input.
        suggested_next_step: Concrete proposal, without claiming it was executed.
        reason: Brief user-facing justification for the proposal.
        clarification_question: Question needed to proceed, or None when clear.
        selected_action_id: Available workflow action matching the proposal.
    """

    model_config = ConfigDict(extra="forbid")

    content_types: list[str]
    user_intent: str
    suggested_next_step: str
    reason: str
    clarification_question: str | None
    selected_action_id: str
