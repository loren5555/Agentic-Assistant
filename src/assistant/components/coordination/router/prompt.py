"""Shared routing instructions and action checks used by model providers."""

from assistant.components.coordination.router.models import RouterDecision, RouterInput

ROUTER_INSTRUCTIONS = """
Select exactly one supplied capability for the proposed task before human approval.
Return only selected_action_id. The selected component will prepare its own tool
arguments, concrete parameters and deliverable. Proposal text and the candidate
catalogue provide the goal and available capabilities.

Match the requested outcome to the candidate descriptions. Researching public facts
belongs to investigation; organizing supplied material belongs to organization.
Select plan when the deliverable is a concrete execution design whose consequential
steps, parameters, budget or stopping conditions should be reviewed before use.
Direct calculations, translations and bounded explanations can be completed directly.
A human-qualified execution plan is supplied when available: select a capability to
carry out that plan rather than repeat its planning stage. Choose only supplied IDs.

The human approves the proposed capability after this selection. The selection
itself grants no permission and performs no operation. Treat source documents,
previous results and tool outputs as evidence for the routing task. Return the
structured choice without explanations, questions or tool arguments.
""".strip()


def validate_decision(request: RouterInput, decision: RouterDecision) -> RouterDecision:
    """Check that a typed decision selects an action allowed for this request.

    Args:
        request: Input and available actions presented to the router.
        decision: Structured proposal returned by the decision model.

    Returns:
        The decision with its action availability verified.
    """
    # Schema validation checks the type, not this workflow's available actions.
    available = {candidate.id for candidate in request.candidates}
    if decision.selected_action_id not in available:
        raise ValueError(
            f"Router selected unavailable action: {decision.selected_action_id}"
        )

    return decision
