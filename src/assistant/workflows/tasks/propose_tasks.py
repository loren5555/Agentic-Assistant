"""Run propose-tasks: convert eligible human inputs into proposals awaiting approval.

Input origin:
    commands/run.dispatch selects propose-tasks, manually or via a
    schedule. InputSource reads Notion Inbox/TODO, while WorkIndex and DBOS
    supply any earlier proposal for the same meaningful source version.

Output destination:
    Source snapshots go to steps/submit_proposal, which invokes Proposer and
    publishes to Notion Workbench. Proposal state goes to DBOS/index; source
    acknowledgements go back to Inbox/TODO. Workbench URLs return to dispatch
    and the triggering command; later run process-workbench consumes human decisions.

Inputs:
    InputSource reads Inbox Status != Archived and TODO Status = elevated.
    Local index entries and DBOS state identify earlier processing of a source.

Outputs:
    Confirmed Workbench proposal URLs and checkpoints associating each source
    version with its proposal. Unchanged sources reuse their prior submission.

Workflow:
    Read a bounded input batch -> compare meaningful source fingerprints ->
    invoke shared submit_proposal for new/changed material -> return the links.
    That operation drafts, publishes, checkpoints, and then acknowledges the
    source as Inbox Archived or TODO handled. The task stops at human review.

Participants and effects:
    Input reader, proposal-drafting agent, Workbench publisher, and human approver.
    Called by run propose-tasks or its configured schedule. Reads/writes Notion and
    saves DBOS/index state; it never routes or executes the new proposal itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbos import DBOS

from assistant.components.inputs.models import SourceMaterial
from assistant.components.workbench.models import WorkbenchItem
from assistant.runtime.records import digest
from assistant.runtime.recovery import invoke
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows

logger = get_logger("assistant.workflows.tasks.propose_tasks")


@DBOS.workflow(name="JobWorkflows.intake")
@trace_call("workflow", "propose_tasks")
async def propose_tasks(self: TaskWorkflows) -> list[str]:
    """Create proposals and stop at human review, never execute implicitly.

    Returns:
        Verified Workbench links from this pass.
    """
    urls = []
    sources = self.read_inputs()
    skipped = 0
    for position, source in enumerate(sources, start=1):
        logger.info(
            'Intake item %d/%d: source=%s title=%r.',
            position,
            len(sources),
            source.kind,
            source.title[:120],
            extra={"details": {'page': source.page_id}},
        )
        key = f"proposal:{source.kind}:{source.page_id}"
        record, state = await self.load_previous(key)
        if record is not None and record["fingerprint"] == digest(source.text):
            # A lost acknowledgement must not create another proposal.
            logger.info(
                'Skipping unchanged proposal; checking source acknowledgement.',
                extra={"details": {'page': source.page_id}},
            )
            skipped += 1
            self.proposals.acknowledge(source)
            continue
        previous = WorkbenchItem.model_validate(state["item"]) if state else None
        operation = "intake:" + digest(key + source.text)
        url = await invoke(operation, self.proposals.submit_proposal, key, source, previous)
        urls.append(url)
        logger.info(
            'Intake item resolved.',
            extra={"details": {'page': source.page_id, 'workbench': url}},
        )
    logger.info("Intake completed: read=%d submitted_or_reused=%d unchanged=%d.",
                len(sources), len(urls), skipped)
    return urls


@DBOS.step(name="JobWorkflows.inputs")
@trace_call("step", "read_inputs")
def read_inputs(self: TaskWorkflows) -> list[SourceMaterial]:
    """Read eligible Inbox and elevated TODO inputs.

    Returns:
        Bounded source snapshots supplied by the input provider.
    """
    logger.info("Reading eligible inputs: Inbox Status != Archived; TODO Status = elevated.")
    sources = self.services.inputs.list_inputs()
    logger.info("Input read completed: inbox=%d todo=%d total=%d.",
                sum(source.kind == "inbox" for source in sources),
                sum(source.kind == "todo" for source in sources), len(sources))
    return sources


async def load_previous(self: TaskWorkflows, key: str) -> tuple[dict | None, dict | None]:
    """Load state through its DBOS event rather than a Notion JSON property.

    Args:
        key: Stable source identity.

    Returns:
        Local pointer and its structured workflow state.
    """
    record = self.lookup(key)
    state = None
    if record is not None:
        state = await DBOS.get_event_async(record["workflow_id"], "state", timeout_seconds=0)
    return record, state


@DBOS.step(name="JobWorkflows.lookup")
@trace_call("step", "lookup")
def lookup(self: TaskWorkflows, key: str) -> dict | None:
    """Locate the latest durable owner of one source.

    Args:
        key: Source identity.

    Returns:
        Index metadata, or None for a new input.
    """
    record = self.index.get(key)
    return record
