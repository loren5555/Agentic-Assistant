"""Retry failed operations without discarding their successful checkpoints."""

from dbos import DBOS


async def recover(workflow_id: str):
    """Resume an interrupted operation or rewind only its failed step.

    Args:
        workflow_id: Persisted workflow identity selected for recovery.

    Returns:
        Handle for the recovered operation.
    """
    status = await DBOS.get_workflow_status_async(workflow_id)
    if status.status == "ERROR":
        steps = await DBOS.list_workflow_steps_async(workflow_id)
        failed = next((step for step in steps if step["error"] is not None), None)
        start_step = failed["function_id"] if failed else max((step["function_id"] for step in steps), default=0) + 1
        if failed and failed["child_workflow_id"]:
            child = await recover(failed["child_workflow_id"])
            await child.get_result()
        handle = await DBOS.rewind_workflow_async(workflow_id, start_step=start_step)
    else:
        handle = await DBOS.resume_workflow_async(workflow_id)
    return handle
