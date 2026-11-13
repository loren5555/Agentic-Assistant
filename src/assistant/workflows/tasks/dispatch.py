"""Dispatch queued manual and scheduled requests into existing business workflows.

Input origin:
    The local service and persisted schedule triggers enqueue named jobs.
Output destination:
    Each business workflow owns its Notion writes; its result is saved by DBOS.
Responsibility:
    Keep the stable JobWorkflows.dispatch identity and existing approval boundaries.
"""

from __future__ import annotations

from time import monotonic
from typing import TYPE_CHECKING

from dbos import DBOS
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows

logger = get_logger("workflows.tasks.dispatch")


@DBOS.workflow(name="JobWorkflows.dispatch")
@trace_call("workflow", "dispatch")
async def dispatch(self: TaskWorkflows, job: str, day: str, page_id: str | None = None):
    """Run one named job and return its actual outputs.

    Args:
        job: Action-and-object task name matching a run subcommand.
        day: Asia/Shanghai date used for daily recommendation identity.
        page_id: Optional raw capture for manual reprocessing.

    Returns:
        Job links or an evidence-grounded recommendation report.
    """
    started = monotonic()
    logger.info(
        "Job started: job=%s day=%s.",
        job,
        day,
        extra={"details": {"workflow": DBOS.workflow_id, "page": page_id or "batch"}},
    )
    try:
        match job:
            case "propose-tasks":
                output = await self.propose_tasks()
            case "process-workbench":
                output = await self.process_workbench()
            case "reconcile-feedback":
                output = await self.reconcile_feedback()
            case "process-signals":
                output = await self.process_signals()
            case "organize-papers":
                output = await self.organize_papers(page_id)
            case "organize-articles":
                output = await self.organize_articles(page_id)
            case (
                "recommend-papers" | "recommend-papers-deep" | "recommend-papers-light"
            ):
                collection_mode = {
                    "recommend-papers": "auto",
                    "recommend-papers-deep": "deep",
                    "recommend-papers-light": "light",
                }[job]
                output = await self.research.daily_newspaper(day, collection_mode)
                logger.info(
                    "Recommendation result: demo=%s selected=%d published=%d rejected=%d source_failures=%d pending_recovery=%d.",
                    output.demo,
                    len(output.selected),
                    len(output.published),
                    len(output.rejected),
                    len(output.source_failures),
                    len(output.pending_recovery),
                )
            case _:
                raise ValueError(f"Unknown job: {job}")
    except Exception:
        logger.exception(
            "Job failed: job=%s elapsed=%.2fs.",
            job,
            monotonic() - started,
            extra={"details": {"workflow": DBOS.workflow_id}},
        )
        raise
    logger.info(
        "Job completed: job=%s elapsed=%.2fs.",
        job,
        monotonic() - started,
        extra={"details": {"workflow": DBOS.workflow_id}},
    )
    return output
