"""Return human feedback to its original source instead of dispatching a redo.

Input origin:
    Managed Workbench clarification answers, revisions, rejections and unqualified results.
Output destination:
    Updated source supplements/history/version, and terminal old-work states.
    Reopened sources are picked up by the normal source workflows on their next run.
Responsibility:
    No drafting, model invocation or execution. All write effects are retry-safe.
"""

from dbos import DBOS
from assistant.components.inputs.models import SourceMaterial
from assistant.components.workbench.models import WorkbenchItem
from assistant.runtime.records import digest
from assistant.runtime.recovery import invoke
from logger import get_logger, trace_call

logger = get_logger("workflows.reconcile_feedback")


@DBOS.workflow(name="JobWorkflows.reconcile_feedback.v2")
@trace_call("workflow", "reconcile_feedback")
async def reconcile_feedback(self) -> list[str]:
    """Poll registered active work for feedback requiring a source update.

    Returns:
        Old Workbench pages closed after reconciliation.
    """
    urls = []
    records = self.list_active()
    logger.info('Collecting human feedback: active_work=%d.', len(records))
    for record in records:
        state = await DBOS.get_event_async(record["workflow_id"], "state", timeout_seconds=0)
        if state is None:
            raise RuntimeError(f"Managed work has no state: {record['workflow_id']}")
        saved = WorkbenchItem.model_validate(state["item"])
        current = self.proposals.read_review(saved)
        pending = current.status in {"Open", "Needs Input"}
        rejected = pending and current.human_review == "Rejected"
        if pending and current.needs_input:
            revised = current.human_review in {"Approved", "Revision Requested"} and bool(current.human_instruction.strip())
            if not (revised or rejected):
                logger.info('Waiting for clarification answer: title=%r; reply in Human Instruction and submit Human Review.', current.title)
        else:
            revised = current.status == "Open" and current.human_review == "Revision Requested"
        unqualified = current.status == "Executed" and current.result_review == "Unqualified"
        # A lost close acknowledgement can leave the local pointer active even
        # though Notion already has the terminal state. Recover its checkpoint too.
        closed = current.status in {"Superseded", "Deprecated"}
        if not (revised or rejected or unqualified or closed):
            continue
        source = SourceMaterial.model_validate(state["source"])
        identity = self.services.reconciler.reconcile(source, current)
        operation = "reconcile:v2:" + digest(current.page_id + identity.model_dump_json())
        urls.append(await invoke(operation, self.proposals.reconcile_item, record["source_key"], source, current))
    logger.info('Feedback collection completed: reconciled=%d.', len(urls))
    return urls


@DBOS.workflow(name="ProposalWorkflows.reconcile_item.v2")
@trace_call("workflow", "reconcile_item")
async def reconcile_item(self, key: str, source: SourceMaterial, item: WorkbenchItem) -> str:
    """Apply one feedback round and checkpoint the closed old task.

    Args:
        key: Original input pointer.
        source: Scope of the reviewed work.
        item: Human decision and previous result.

    Returns:
        Closed Workbench page URL.
    """
    item = self.apply_reconciliation(source, item)
    await self.save_checkpoint(key, source, item)
    return item.url


@DBOS.step(name="ProposalWorkflows.apply_reconciliation.v2")
@trace_call("step", "apply_reconciliation")
def apply_reconciliation(self, source: SourceMaterial, item: WorkbenchItem) -> WorkbenchItem:
    """Write feedback first, then close old work; retry either safely.

    Args:
        source: Original source version.
        item: Review snapshot authorizing reconciliation.

    Returns:
        Old item marked Superseded or Deprecated.
    """
    decision = self.services.reconciler.reconcile(source, item)
    current = self.services.workbench.read_item(item.page_id)
    if current.status == decision.status:
        return item.model_copy(update={"status": decision.status})
    fields = ("status", "human_review", "human_instruction", "result_review", "result_feedback", "publication_key")
    if any(getattr(current, field) != getattr(item, field) for field in fields):
        raise RuntimeError("Human feedback changed during reconciliation")
    if decision.feedback is not None:
        updated = self.services.processor(source.kind).apply_feedback(source, decision.feedback)
        logger.info('Feedback returned to source: title=%r version=%d; awaiting normal intake.', updated.title, updated.version)
    self.services.workbench.set_status(item, decision.status)
    item = item.model_copy(update={"status": decision.status})
    logger.info('Old work closed: title=%r status=%s.', item.title, item.status)
    return item
