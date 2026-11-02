"""Share proposal submission across intake, capture escalation, and revision.

Input origin:
    intake passes Inbox/TODO material from InputSource. organize_capture
    can adapt a Notero/SimpRead record into SourceMaterial. reviews
    supplies revised sources and Workbench feedback when a proposal needs revision.

Output destination:
    The draft goes to a DBOS step checkpoint, then Workbench.submit/revise
    publishes the report in Notion Workbench. Source/item state goes to DBOS and
    WorkIndex; eligible source acknowledgements go to Inbox/TODO/SimpRead. The
    Workbench URL returns to the parent workflow and awaits human approval.

Inputs:
    Stable source key, SourceMaterial snapshot, and optional prior WorkbenchItem
    carrying the previous proposal and human feedback.

Outputs:
    Confirmed Workbench URL plus a DBOS state event and local index pointer for
    the source/proposal version. Successful submission acknowledges the raw input.

Workflow:
    Draft and checkpoint the Proposal -> reread source and relevant human fields
    -> submit or revise through Workbench -> save the resulting machine state ->
    acknowledge the original source. Model drafting and publication have separate
    checkpoints so a write failure does not require repeating a successful draft.

Participants and effects:
    Parent intake/capture/review workflows, proposal-drafting agent, input source,
    Workbench publisher, and human approver. Publication confirmation uses the
    Workbench property receipt; source acknowledgement follows the saved state.
    Inbox/TODO/SimpRead may be acknowledged; raw Notero remains read-only.

Boundaries:
    This operation ends at human approval, not task execution. Functions are
    bound to WorkbenchWorkflows by runtime/application.py; callers determine
    operation identity and timing, while plugins own individual service calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import json

from dbos import DBOS

from assistant.components.inputs.models import SourceMaterial
from assistant.components.proposer.models import Proposal
from assistant.components.workbench.models import WorkbenchItem
from assistant.runtime.records import digest, capture_material
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import WorkbenchWorkflows

logger = get_logger("assistant.workflows.steps.submit_proposal")


@DBOS.workflow(name="ProposalWorkflows.intake_item")
@trace_call("workflow", "submit_proposal")
async def submit_proposal(self: WorkbenchWorkflows, key: str, source: SourceMaterial, previous: WorkbenchItem | None = None) -> str:
    """Publish one source proposal and end at the human approval boundary.

    Args:
        key: Stable raw input key.
        source: Captured material for this intake version.
        previous: Existing managed report if this input is being reorganized.

    Returns:
        Verified Workbench URL.
    """
    logger.info(
        'Proposal intake started.',
        extra={"details": {'source_page': source.page_id, 'workflow': DBOS.workflow_id}},
    )
    proposal = await self.draft(source, previous)
    item = self.publish_proposal(source, proposal, previous)
    await self.save_checkpoint(key, source, item)
    self.acknowledge(source)
    logger.info(
        'Proposal intake completed; waiting for human approval.',
        extra={"details": {'source_page': source.page_id, 'workbench': item.url}},
    )
    return item.url


@DBOS.step(name="ProposalWorkflows.draft")
@trace_call("step", "draft")
async def draft(self: WorkbenchWorkflows, source: SourceMaterial, previous: WorkbenchItem | None = None) -> Proposal:
    """Checkpoint one provider draft separately from external publication.

    Args:
        source: Grounded input material.
        previous: Report and human feedback when revising.

    Returns:
        Provider-generated proposal.
    """
    logger.info(
        'Drafting proposal: title=%r source=%s mode=%s.',
        source.title,
        source.kind,
        'revision' if previous else 'new',
        extra={"details": {'page': source.page_id}},
    )
    proposal = await self.services.proposer.draft(source, previous)
    logger.info(
        'Proposal drafted: title=%r version=%d plan_steps=%d.',
        proposal.title,
        proposal.version,
        len(proposal.plan),
        extra={"details": {'source_page': source.page_id}},
    )
    return proposal


@DBOS.step(name="ProposalWorkflows.publish_proposal")
@trace_call("step", "publish_proposal")
def publish_proposal(self: WorkbenchWorkflows, source: SourceMaterial, proposal: Proposal, previous: WorkbenchItem | None = None) -> WorkbenchItem:
    """Publish and re-fetch one proposal with its confirmation property.

    Args:
        source: Original input.
        proposal: Checkpointed draft.
        previous: Workbench item when updating rather than creating.

    Returns:
        Verified page retaining the runtime payload.
    """
    logger.info(
        'Publishing proposal: title=%r version=%d updating=%s.',
        proposal.title,
        proposal.version,
        previous is not None,
        extra={"details": {'source_page': source.page_id}},
    )
    if self.read_current_source(source).text != source.text:
        raise RuntimeError("Source changed during proposal drafting")
    if previous is None:
        item = self.services.workbench.submit(source, proposal, DBOS.workflow_id)
    else:
        current = self.services.workbench.read_item(previous.page_id)
        expected_key = "proposal:" + digest(proposal.model_dump_json(exclude={"process"}))
        if current.publication_key == expected_key and current.publication_applied and current.status == "Open":
            item = self.services.workbench.revise(previous, proposal)
        else:
            fields = ("human_review", "human_instruction", "result_review", "result_feedback")
            partial = current.publication_key == expected_key
            checked = ("human_instruction", "result_feedback") if partial else fields
            if any(getattr(current, field) != getattr(previous, field) for field in checked):
                raise RuntimeError("Human review changed during proposal drafting")
            if current.publication_key != previous.publication_key and current.publication_key != expected_key:
                raise RuntimeError("Report publication changed during proposal drafting")
            if self.read_current_source(source).text != source.text:
                raise RuntimeError("Source changed during proposal drafting")
            item = self.services.workbench.revise(previous, proposal)
    item.proposal = proposal
    item.source_kind = source.kind
    logger.info(
        'Proposal publication verified: title=%r version=%d status=%s.',
        item.title,
        proposal.version,
        item.status,
        extra={"details": {'page': item.page_id}},
    )
    return item


@DBOS.step(name="ProposalWorkflows.checkpoint")
@trace_call("step", "save_checkpoint")
async def save_checkpoint(self: WorkbenchWorkflows, key: str, source: SourceMaterial, item: WorkbenchItem) -> None:
    """Save machine state in DBOS before advancing its local index pointer.

    Args:
        key: Stable raw input identity.
        source: Input scope represented by the proposal.
        item: Current report, deliverable, extraction, and human decisions.
    """
    state = {"source": source.model_dump(mode="json"), "item": item.model_dump(mode="json")}
    traces = {"proposal": item.proposal.process if item.proposal else None, "result": item.result.process if item.result else None}
    report_directory = self.directory / "process"
    report_directory.mkdir(parents=True, exist_ok=True)
    traces = {name: value.model_dump(mode="json") for name, value in traces.items() if value is not None}
    if traces:
        path = report_directory / f"{digest(DBOS.workflow_id)}.json"
        path.write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    await DBOS.set_event_async("state", state)
    self.index.save(key, digest(source.text), DBOS.workflow_id, item.page_id, item.status)
    logger.debug(
        'Business state checkpoint saved: status=%s.',
        item.status,
        extra={"details": {'page': item.page_id, 'workflow': DBOS.workflow_id}},
    )


@DBOS.step(name="ProposalWorkflows.acknowledge")
@trace_call("step", "acknowledge")
def acknowledge(self: WorkbenchWorkflows, source: SourceMaterial) -> None:
    """Close raw intake only after its destination is verified.

    Args:
        source: Original source to acknowledge.
    """
    if source.kind in {"inbox", "todo"}:
        if self.read_current_source(source).text != source.text:
            raise RuntimeError("Source changed before intake acknowledgement")
        self.services.inputs.close_source(source)
    elif source.kind == "simpread":
        capture = self.services.captures.read_capture(source.page_id, source.kind)
        if capture_material(capture).text != source.text:
            raise RuntimeError("Capture changed before proposal acknowledgement")
        self.services.captures.mark_handled(capture)


@DBOS.step(name="ProposalWorkflows.read_source")
@trace_call("step", "read_source")
def read_source(self: WorkbenchWorkflows, source: SourceMaterial) -> SourceMaterial:
    """Refresh the raw input while respecting independent source interfaces.

    Args:
        source: Source identity retained in DBOS.

    Returns:
        Current meaningful source material.
    """
    current = self.read_current_source(source)
    return current


def read_current_source(self: WorkbenchWorkflows, source: SourceMaterial) -> SourceMaterial:
    """Read live scope without reusing an earlier checkpoint during writes.

    Args:
        source: Raw input identity.

    Returns:
        Current material for an authorization comparison.
    """
    if source.kind in {"notero", "simpread"}:
        capture = self.services.captures.read_capture(source.page_id, source.kind)
        current = capture_material(capture)
    else:
        current = self.services.inputs.read_source(source.url)
    return current
