"""Draft, publish, verify, and checkpoint one source proposal."""

from __future__ import annotations

from typing import TYPE_CHECKING
import json

from dbos import DBOS

from assistant.components.inputs.models import SourceMaterial
from assistant.components.proposer.models import Proposal
from assistant.components.workbench.models import WorkbenchItem
from assistant.runtime.records import digest, capture_material
from logger import get_logger

if TYPE_CHECKING:
    from assistant.runtime.application import WorkbenchWorkflows

logger = get_logger("assistant.workflows.steps.submit_proposal")


@DBOS.workflow(name="ProposalWorkflows.intake_item")
async def submit_proposal(self: WorkbenchWorkflows, key: str, source: SourceMaterial, previous: WorkbenchItem | None = None) -> str:
    """Publish one source proposal and end at the human approval boundary.

    Args:
        key: Stable raw input key.
        source: Captured material for this intake version.
        previous: Existing managed report if this input is being reorganized.

    Returns:
        Verified Workbench URL.
    """
    logger.info("Proposal intake started: source_page=%s workflow=%s.", source.page_id, DBOS.workflow_id)
    proposal = await self.draft(source, previous)
    item = self.publish_proposal(source, proposal, previous)
    await self.save_checkpoint(key, source, item)
    self.acknowledge(source)
    logger.info("Proposal intake completed: source_page=%s workbench=%s; waiting for human approval.", source.page_id, item.url)
    return item.url


@DBOS.step(name="ProposalWorkflows.draft")
async def draft(self: WorkbenchWorkflows, source: SourceMaterial, previous: WorkbenchItem | None = None) -> Proposal:
    """Checkpoint one provider draft separately from external publication.

    Args:
        source: Grounded input material.
        previous: Report and human feedback when revising.

    Returns:
        Provider-generated proposal.
    """
    logger.info("Drafting proposal: source=%s page=%s mode=%s.",
                source.kind, source.page_id, "revision" if previous else "new")
    proposal = await self.services.proposer.draft(source, previous)
    logger.info("Proposal drafted: source_page=%s version=%d plan_steps=%d.", source.page_id, proposal.version, len(proposal.plan))
    return proposal


@DBOS.step(name="ProposalWorkflows.publish_proposal")
def publish_proposal(self: WorkbenchWorkflows, source: SourceMaterial, proposal: Proposal, previous: WorkbenchItem | None = None) -> WorkbenchItem:
    """Publish and re-fetch one proposal with its confirmation property.

    Args:
        source: Original input.
        proposal: Checkpointed draft.
        previous: Workbench item when updating rather than creating.

    Returns:
        Verified page retaining the runtime payload.
    """
    logger.info("Publishing proposal: source_page=%s version=%d updating=%s.", source.page_id, proposal.version, previous is not None)
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
    logger.info("Proposal publication verified: page=%s version=%d status=%s.", item.page_id, proposal.version, item.status)
    return item


@DBOS.step(name="ProposalWorkflows.checkpoint")
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
    logger.debug("Business state checkpoint saved: page=%s status=%s workflow=%s.",
                 item.page_id, item.status, DBOS.workflow_id)


@DBOS.step(name="ProposalWorkflows.acknowledge")
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
