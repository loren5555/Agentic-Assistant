"""Persist manual and scheduled tasks before acknowledging their submission.

Input origin: validated local API requests or DBOS schedule callbacks.
Output destination: the serial assistant-jobs queue and durable workflow handles.
Recovery requests use a separate control queue so waiting for recovered queued
work never consumes that work's execution slot. Existing version checks apply.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from dbos import DBOS, SetWorkflowID, SetWorkflowAttributes

from assistant.runtime.recovery import recover
from assistant.runtime.service.models import JobSubmission
from logger import get_logger, trace_call

JOB_QUEUE = "assistant-jobs"
TRIGGER_QUEUE = "assistant-triggers"
RECOVERY_QUEUE = "assistant-recovery"
logger = get_logger("runtime.service.submissions")


async def enqueue_job(application, job: str, day: str, page: str | None = None, exploration_round: str | None = None):
    """Queue a dispatch from either trigger, preserving business arguments."""
    extra = (exploration_round,) if exploration_round else ()
    with SetWorkflowAttributes({"job": job, "page": page or "batch"}):
        return await DBOS.enqueue_workflow_async(
            JOB_QUEUE, application.tasks.dispatch, job, day, page, *extra
        )


async def submit_job(application, request: JobSubmission):
    """Reuse an acknowledged request or durably enqueue exactly one new dispatch."""
    workflow_id = f"manual:{request.request_id}"
    exploration_round = str(request.request_id) if request.refresh else None
    existing = await DBOS.get_workflow_status_async(workflow_id)
    if existing:
        args = existing.input["args"]
        if args[0] != request.job or args[2] != request.page or bool(args[3:]) != request.refresh:
            raise ValueError("Request ID already belongs to a different job, page or refresh mode")
        logger.info(
            "Task submission already recorded: job=%s.",
            request.job,
            extra={"details": {"workflow": workflow_id}},
        )
        return workflow_id
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    with SetWorkflowID(workflow_id):
        handle = await enqueue_job(application, request.job, day, request.page, exploration_round)
    logger.info(
        "Task queued: job=%s.",
        request.job,
        extra={"details": {"workflow": handle.workflow_id, "page": request.page}},
    )
    return handle.workflow_id


@DBOS.workflow(name="recover_requested_workflow")
@trace_call("workflow", "recover_requested_workflow")
async def recover_requested_workflow(workflow_id: str):
    """Complete an operator-requested recovery independently of the HTTP caller."""
    logger.info("Recovery started.", extra={"details": {"workflow": workflow_id}})
    handle = await recover(workflow_id)
    result = await handle.get_result()
    logger.info("Recovery completed.", extra={"details": {"workflow": workflow_id}})
    return result
