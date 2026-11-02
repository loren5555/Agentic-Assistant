"""Retry failed operations without discarding their successful checkpoints."""

from dbos import DBOS, WorkflowStatus
from dbos import SetWorkflowID

from logger import get_logger


def check_version(status: WorkflowStatus) -> None:
    """Reject unfinished work tied to another application version.

    Args:
        status: Persisted workflow state selected for reuse or recovery.
    """
    if status.status == "SUCCESS":
        return
    current = DBOS.application_version
    if status.app_version is not None and status.app_version != current:
        logger.error(
            'kind=checkpoint Workflow version mismatch: status=%s.',
            status.status,
            extra={"details": {'workflow': status.workflow_id, 'stored_version': status.app_version, 'current_version': current}},
        )
        raise RuntimeError(
            f"Workflow {status.workflow_id} belongs to version {status.app_version}, "
            f"but this process runs {current}. Stop the runtime and explicitly "
            "delete the obsolete unfinished workflow before starting again; "
            "no automatic migration or deletion was performed."
        )


async def recover(workflow_id: str):
    """Resume an interrupted operation or rewind only its failed step.

    Args:
        workflow_id: Persisted workflow identity selected for recovery.

    Returns:
        Handle for the recovered operation.
    """
    logger = get_logger("runtime.recovery")
    logger.debug(
        'kind=checkpoint Inspecting workflow for recovery.',
        extra={"details": {'workflow': workflow_id}},
    )
    status = await DBOS.get_workflow_status_async(workflow_id)
    check_version(status)
    logger.debug(
        'kind=checkpoint Recovery status: status=%s.',
        status.status,
        extra={"details": {'workflow': workflow_id}},
    )
    if status.status == "ERROR":
        steps = await DBOS.list_workflow_steps_async(workflow_id)
        failed = next((step for step in steps if step["error"] is not None), None)
        start_step = failed["function_id"] if failed else max((step["function_id"] for step in steps), default=0) + 1
        if failed and failed["child_workflow_id"]:
            logger.warning(
                'kind=checkpoint Recovering failed child before parent.',
                extra={"details": {'parent': workflow_id, 'child': failed['child_workflow_id']}},
            )
            child = await recover(failed["child_workflow_id"])
            await child.get_result()
        logger.warning(
            'kind=checkpoint Rewinding failed workflow: start_step=%d; earlier successful checkpoints retained.',
            start_step,
            extra={"details": {'workflow': workflow_id}},
        )
        handle = await DBOS.rewind_workflow_async(workflow_id, start_step=start_step)
    else:
        logger.info(
            'kind=checkpoint Requesting DBOS resume: status=%s.',
            status.status,
            extra={"details": {'workflow': workflow_id}},
        )
        handle = await DBOS.resume_workflow_async(workflow_id)
    return handle


logger = get_logger("runtime.recovery")


async def invoke(workflow_id: str, function, *args):
    """Reuse an operation identity and resume its incomplete steps on retry.

    Args:
        workflow_id: Deterministic operation identity.
        function: Registered workflow method.
        args: Serializable business inputs.

    Returns:
        Completed workflow output.
    """
    status = await DBOS.get_workflow_status_async(workflow_id)
    logger.debug(
        'kind=checkpoint Resolving durable operation: stored_status=%s.',
        status.status if status else 'new',
        extra={"details": {'workflow': workflow_id}},
    )
    if status is not None:
        check_version(status)
    if status is not None and status.status == "ERROR":
        handle = await recover(workflow_id)
    elif status is not None:
        if status.status == "SUCCESS":
            logger.info(
                'kind=checkpoint Reusing completed workflow result; no agent or script rerun.',
                extra={"details": {'workflow': workflow_id}},
            )
        else:
            logger.info(
                'kind=checkpoint Waiting for existing workflow: status=%s; no duplicate start.',
                status.status,
                extra={"details": {'workflow': workflow_id}},
            )
        handle = await DBOS.retrieve_workflow_async(workflow_id, existing_workflow=False)
    else:
        with SetWorkflowID(workflow_id):
            handle = await DBOS.start_workflow_async(function, *args)
    output = await handle.get_result()
    logger.debug(
        'kind=checkpoint Durable operation completed.',
        extra={"details": {'workflow': workflow_id}},
    )
    return output
