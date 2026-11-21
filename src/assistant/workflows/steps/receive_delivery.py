"""Receive work completed elsewhere for ordinary Workbench result review.

Input origin:
    A human submits the report section of an open, versioned proposal.
Output destination:
    Workbench receives the report and its evidence links as a pending result.
Responsibility:
    Check the reviewed action's delivery contract and bind one submitted snapshot
    to its publication receipt. The normal review workflow handles acceptance.
"""

import json

from dbos import DBOS

from assistant.components.coordination.router.actions import supports_external_report
from assistant.components.data.sources.models import SourceMaterial
from assistant.components.data.workbench.models import WorkbenchItem, result_publication_key
from assistant.components.data.workbench.protocol import ExternalReportError
from assistant.components.execution.task_worker.models import TaskResult
from assistant.runtime.records import digest
from assistant.runtime.recovery import invoke
from logger import get_logger, trace_call

logger = get_logger("workflows.receive_delivery")


@DBOS.step(name="ProposalWorkflows.read_delivery")
@trace_call("step", "read_delivery")
def read_delivery(self, saved: WorkbenchItem, current: WorkbenchItem) -> TaskResult | None:
    """Capture the reviewed report or leave a correction on the open proposal."""
    logger.info("Reading submitted report: title=%r.", current.title)
    proposal = saved.proposal
    action = proposal.selected_action if proposal else None
    try:
        if not action or proposal.kind != "execution" or not supports_external_report(action.id):
            raise ExternalReportError("This proposal requires its designated workflow. Choose Approved to run it or request a revision.")
        if (current.selected_action_id != action.id or current.proposal_version != proposal.version
                or current.publication_key != saved.publication_key):
            raise ExternalReportError("The proposal version, selected action or publication changed. Review the current proposal before submitting.")
        content = self.services.workbench.read_external_report(current.page_id)
        if not content.strip():
            raise ExternalReportError("Add your completed report and evidence under the External report heading, then run process-workbench.")
    except ExternalReportError as error:
        if current.execution_error != str(error):
            self.services.workbench.save_error(current, str(error))
        logger.warning("External delivery needs attention: title=%r. %s", current.title, error)
        return None
    logger.info("Submitted report read: title=%r characters=%d.", current.title, len(content))
    return TaskResult(content=content, delivery_source="external", action_id=action.id)


async def process_delivery(self, record: dict, state: dict, saved: WorkbenchItem, current: WorkbenchItem) -> str | None:
    """Start a receipt-bound delivery, or resume its snapshot after Notion confirmed it."""
    result = None
    if current.status == "Open":
        result = self.proposals.read_delivery(saved, current)
        if result is None:
            return None
        receipt = result_publication_key(saved.proposal.version, result.model_dump_json(exclude={"action_id", "process"}))
    else:
        receipt = current.publication_key
    operation = "delivery:" + digest(json.dumps([record["workflow_id"], saved.publication_key, receipt]))
    if result is None and await DBOS.get_workflow_status_async(operation) is None:
        logger.warning("Could not match submitted result to a saved delivery: title=%r.", current.title)
        return None
    source = SourceMaterial.model_validate(state["source"])
    return await invoke(operation, self.proposals.receive_delivery, record["source_key"], source, current, result)


@DBOS.workflow(name="ProposalWorkflows.receive_delivery")
@trace_call("workflow", "receive_delivery")
async def receive_delivery(self, key: str, source: SourceMaterial, item: WorkbenchItem, result: TaskResult) -> str:
    """Save the submitted snapshot and its resulting Workbench state for acceptance."""
    logger.info("Receiving externally completed work: title=%r.", item.title)
    current = self.save_result(source, item, result)
    await self.save_checkpoint(key, source, current)
    logger.info("External result received for review: title=%r.", current.title)
    return current.url
