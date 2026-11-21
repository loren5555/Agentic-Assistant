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

from assistant.components.data.sources.models import SourceMaterial
from assistant.components.coordination.proposer.models import Proposal
from assistant.components.coordination.router.actions import AMINER_RESEARCH, EXECUTION_ACTIONS
from assistant.components.coordination.router.models import ActionCandidate, RouterInput
from assistant.components.coordination.router.prompt import validate_decision
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
    if proposal.kind == "retention":
        route = ActionCandidate(id="retain_material", name="Retain reviewed material",
                                description="On approval Curator and Publisher archive the displayed material.")
        return proposal.model_copy(update={"selected_action": route})
    candidates = [candidate for candidate in EXECUTION_ACTIONS
                  if candidate.id != "plan" or proposal.execution_plan is None]
    if self.services.aminer_api_key:
        candidates.append(AMINER_RESEARCH)
    request = RouterInput(text=proposal.model_dump_json(exclude={"process", "routing_process"}),
                          context=[source.context_content], candidates=candidates)
    logger = get_logger("workflows.select_action")
    logger.info("Selecting proposed workflow: title=%r candidates=%d.", proposal.title, len(candidates))
    decision = validate_decision(request, await self.services.router.decide(request))
    selected = next(candidate for candidate in candidates if candidate.id == decision.selected_action_id)
    logger.info("Proposed workflow selected: title=%r workflow=%s; awaiting human approval.",
                proposal.title, selected.name or selected.id)
    return proposal.model_copy(update={"selected_action": selected, "routing_process": decision.process})
