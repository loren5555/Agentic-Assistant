"""Return a human-qualified plan to its source for fresh execution approval.

Input origin:
    An Executed planning task whose Result Review is Qualified in Workbench.
Output destination:
    The original source receives the accepted plan/history as a new version.
    The completed planning item becomes Finished. Shared intake then publishes
    a separate execution proposal referring to the plan.
Responsibility:
    Preserve the qualified plan, apply one retry-safe source update and finish
    the planning task. Qualification approves the plan as input to the next
    proposal; execution follows that proposal's separate approval.
"""

from dbos import DBOS

from assistant.components.inputs.models import SourceHistory, SourceMaterial
from assistant.components.workbench.models import WorkbenchItem
from assistant.runtime.records import digest
from logger import get_logger, trace_call


@DBOS.step(name="ProposalWorkflows.accept_plan")
@trace_call("step", "accept_plan")
def accept_plan(self, source: SourceMaterial, item: WorkbenchItem) -> SourceMaterial:
    """Apply a qualified plan once and return the effective next source.

    Args:
        source: Source snapshot used for the completed planning task.
        item: Human-qualified planning result and saved capability.

    Returns:
        Reopened source carrying the accepted plan for a new execution proposal.
    """
    if item.result is None or item.result.plan is None or item.result.action_id != "plan":
        raise ValueError("A qualified planning result must contain a concrete plan")
    current = self.services.workbench.read_item(item.page_id)
    fields = ("human_review", "human_instruction", "result_review", "result_feedback",
              "publication_key", "selected_action_id", "proposal_version")
    if current.status not in {"Executed", "Finished"} or current.result_review != "Qualified":
        raise RuntimeError("Plan acceptance changed before follow-up")
    if any(getattr(current, field) != getattr(item, field) for field in fields):
        raise RuntimeError("Human review or planned scope changed before follow-up")

    feedback = SourceHistory(
        key="accepted-plan:" + digest(item.page_id + item.publication_key),
        workbench_url=item.url,
        feedback="\n\n".join(part for part in [
            "The human qualified this execution plan. Prepare a new proposal to carry it out "
            "within its stated scope and limits, for fresh approval before execution.",
            item.human_instruction, item.result_feedback,
        ] if part),
        proposal=item.proposal.model_dump_json(exclude={"process", "routing_process"}),
        result=item.result.model_dump_json(exclude={"process"}),
        accepted_plan=item.result.plan,
    )
    processor = self.services.processor(source.kind)
    current_source = processor.read(source)
    applied = any(entry.key == feedback.key for entry in current_source.history)
    if not applied and current_source.fingerprint != source.fingerprint:
        raise RuntimeError("Source changed before its execution plan was accepted")
    logger = get_logger("workflows.advance_plan")
    logger.info("Accepting plan: title=%r; preparing source for a fresh execution proposal.", item.title)
    updated = processor.apply_feedback(source, feedback)
    if current.status != "Finished":
        self.services.workbench.set_status(item, "Finished")
    logger.info("Plan accepted: title=%r source_version=%d; execution still requires fresh approval.",
                item.title, updated.version)
    return updated
