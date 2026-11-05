"""Checkpoint shared interpretation, planning and proposal publication.

Input origin:
    Any source processor supplies an effective SourceMaterial version.
Output destination:
    Organizer interpretation goes to Proposer, its report goes to Workbench,
    and source acknowledgement follows verified publication and state persistence.
Responsibility:
    Every changed source is a fresh proposal. Old reports remain historical;
    revision feedback lives on the source rather than a special drafting path.
    This workflow ends at approval and never publishes final knowledge directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import json

from dbos import DBOS

from assistant.components.data.sources.models import SourceMaterial
from assistant.components.coordination.proposer.models import Proposal
from assistant.components.data.workbench.models import WorkbenchItem
from assistant.runtime.records import digest
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import WorkbenchWorkflows

logger = get_logger("assistant.workflows.steps.submit_proposal")


@DBOS.workflow(name="ProposalWorkflows.intake_item")
@trace_call("workflow", "submit_proposal")
async def submit_proposal(self: WorkbenchWorkflows, key: str, source: SourceMaterial) -> str:
    """Publish one source proposal and end at the human approval boundary.

    Args:
        key: Stable raw input key.
        source: Captured material for this intake version.

    Returns:
        Verified Workbench URL.
    """
    logger.info(
        'Proposal intake started.',
        extra={"details": {'source_page': source.page_id, 'workflow': DBOS.workflow_id}},
    )
    source = await self.organize_source(source)
    proposal = await self.draft(source)
    proposal = await self.select_action(source, proposal)
    item = self.publish_proposal(source, proposal)
    await self.save_checkpoint(key, source, item)
    self.acknowledge(source)
    logger.info(
        'Proposal intake completed: title=%r status=%s; waiting for human %s.',
        item.title, item.status, "input" if item.needs_input else "approval",
        extra={"details": {'source_page': source.page_id, 'workbench': item.url}},
    )
    return item.url


@DBOS.step(name="ProposalWorkflows.organize_source")
@trace_call("step", "organize_source")
async def organize_source(self: WorkbenchWorkflows, source: SourceMaterial) -> SourceMaterial:
    """Checkpoint shared interpretation before proposal drafting.

    Args:
        source: Complete effective input version.

    Returns:
        The same source with a derived interpretation for Proposer.
    """
    interpretation = await self.services.organizer.organize(source)
    return source.model_copy(update={"organization": interpretation.model_dump_json()})


@DBOS.step(name="ProposalWorkflows.draft")
@trace_call("step", "draft")
async def draft(self: WorkbenchWorkflows, source: SourceMaterial) -> Proposal:
    """Checkpoint one provider draft separately from external publication.

    Args:
        source: Grounded input material.

    Returns:
        Provider-generated proposal.
    """
    logger.info(
        'Drafting proposal: title=%r source=%s version=%d.',
        source.title,
        source.kind,
        source.version,
        extra={"details": {'page': source.page_id}},
    )
    proposal = await self.services.proposer.draft(source)
    if source.history:
        proposal.execution_plan = source.history[-1].accepted_plan
    logger.info(
        'Proposal drafted: title=%r version=%d proposal_kind=%s plan_steps=%d questions=%d.',
        proposal.title,
        proposal.version,
        proposal.kind,
        len(proposal.plan),
        len(proposal.questions),
        extra={"details": {'source_page': source.page_id}},
    )
    return proposal


@DBOS.step(name="ProposalWorkflows.publish_proposal")
@trace_call("step", "publish_proposal")
def publish_proposal(self: WorkbenchWorkflows, source: SourceMaterial, proposal: Proposal) -> WorkbenchItem:
    """Publish and re-fetch one proposal with its confirmation property.

    Args:
        source: Original input.
        proposal: Checkpointed draft.

    Returns:
        Verified page retaining the runtime payload.
    """
    logger.info(
        'Publishing proposal: title=%r version=%d.',
        proposal.title,
        proposal.version,
        extra={"details": {'source_page': source.page_id}},
    )
    if self.read_current_source(source).fingerprint != source.fingerprint:
        raise RuntimeError("Source changed during proposal drafting")
    # Every changed input is a fresh proposal; previous work remains history.
    item = self.services.workbench.submit(source, proposal, DBOS.workflow_id)
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
    traces = {"proposal": item.proposal.process if item.proposal else None,
              "routing": item.proposal.routing_process if item.proposal else None,
              "result": item.result.process if item.result else None}
    report_directory = self.directory / "process"
    report_directory.mkdir(parents=True, exist_ok=True)
    traces = {name: value.model_dump(mode="json") for name, value in traces.items() if value is not None}
    if traces:
        path = report_directory / f"{digest(DBOS.workflow_id)}.json"
        path.write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    await DBOS.set_event_async("state", state)
    self.index.save(key, source.fingerprint, DBOS.workflow_id, item.page_id, item.status)
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
    self.services.processor(source.kind).acknowledge(source)


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
    current = self.services.processor(source.kind).read(source)
    return current
