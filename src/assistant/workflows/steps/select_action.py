"""Select and checkpoint the capability displayed before proposal approval.

Input origin:
    Shared intake supplies Proposer's draft and the effective source snapshot.
Output destination:
    The selected capability snapshot accompanies the proposal to Workbench.
Responsibility:
    Route execution proposals once before review. Clarification proposals target
    the human directly. Executors prepare their own parameters after approval.
"""

from dbos import DBOS

from assistant.components.inputs.models import SourceMaterial
from assistant.components.proposer.models import Proposal
from assistant.components.router.actions import EXECUTION_ACTIONS
from assistant.components.router.models import RouterInput
from assistant.components.router.prompt import validate_decision
from logger import get_logger, trace_call


@DBOS.step(name="ProposalWorkflows.select_action")
@trace_call("step", "select_action")
async def select_action(self, source: SourceMaterial, proposal: Proposal) -> Proposal:
    """Attach one available capability to the proposal before publication.

    Args:
        source: Effective material and previous accepted plans.
        proposal: Draft whose meaning and intended deliverable are established.

    Returns:
        A proposal with the selected capability and actual routing telemetry.
    """
    if proposal.kind == "clarification":
        return proposal
    candidates = [candidate for candidate in EXECUTION_ACTIONS
                  if candidate.id != "plan" or proposal.execution_plan is None]
    request = RouterInput(text=proposal.model_dump_json(exclude={"process", "routing_process"}),
                          context=[source.context_content], candidates=candidates)
    logger = get_logger("workflows.select_action")
    logger.info("Selecting proposed workflow: title=%r candidates=%d.", proposal.title, len(candidates))
    decision = validate_decision(request, await self.services.router.decide(request))
    selected = next(candidate for candidate in candidates if candidate.id == decision.selected_action_id)
    logger.info("Proposed workflow selected: title=%r workflow=%s; awaiting human approval.",
                proposal.title, selected.name or selected.id)
    return proposal.model_copy(update={"selected_action": selected, "routing_process": decision.process})
