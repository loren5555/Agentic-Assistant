"""Dispatch one named business workflow and display its actual result.

Input origin:
    run JOB or a configured schedule selects an input, review, feedback or recommendation job.
Output destination:
    The selected task owns Notion effects; run displays its links/report as JSON.
Responsibility:
    Use the same task entry points for manual and scheduled work. Proposal intake
    never executes implicitly. Daily recommendation is independent of Workbench.
"""

from __future__ import annotations

from datetime import datetime
from time import monotonic
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json

from dbos import DBOS
from pydantic import BaseModel

from assistant.components.recommendations.recommender.models import CATEGORIES, RecommendationRun
from assistant.runtime.recovery import invoke
from logger import get_logger, trace_call

logger = get_logger("commands.run")


if TYPE_CHECKING:
    from assistant.runtime.application import Application, TaskWorkflows


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
        'Job started: job=%s day=%s.',
        job,
        day,
        extra={"details": {'workflow': DBOS.workflow_id, 'page': page_id or 'batch'}},
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
            case "recommend-papers":
                mode = "demo" if self.services.config.providers.discovery == "demo" else "real"
                policy = self.services.config.runtime.recommendations.model_dump_json()
                topic_file = self.research.directory / "recommendation-topics.json"
                if topic_file.exists():
                    policy += topic_file.read_text()
                policy_key = hashlib.sha256(policy.encode()).hexdigest()[:12]
                output = await invoke(f"recommendations:pool-v1:{mode}:{day}:{policy_key}", self.research.recommend_papers, day)
                logger.info("Recommendation result: demo=%s selected=%d published=%d rejected=%d source_failures=%d pending_recovery=%d.",
                            output.demo, len(output.selected), len(output.published), len(output.rejected),
                            len(output.source_failures), len(output.pending_recovery))
            case _:
                raise ValueError(f"Unknown job: {job}")
    except Exception:
        logger.exception(
            'Job failed: job=%s elapsed=%.2fs.',
            job,
            monotonic() - started,
            extra={"details": {'workflow': DBOS.workflow_id}},
        )
        raise
    logger.info(
        'Job completed: job=%s elapsed=%.2fs.',
        job,
        monotonic() - started,
        extra={"details": {'workflow': DBOS.workflow_id}},
    )
    return output


def display(output) -> None:
    """Print business outputs without exposing configuration or model credentials.

    Args:
        output: Workflow report or collection of verified destination links.
    """
    document = output.model_dump(mode="json") if isinstance(output, BaseModel) else output
    if isinstance(output, RecommendationRun):
        # Detailed provider events remain in the durable/local report, while the
        # command output stays focused on recommendations and source limitations.
        document = output.model_dump(mode="json", exclude={
            "failed_processes": True,
            "discovery": {"process"},
            "evidence": {"__all__": {"process"}},
            "selected": {"__all__": {"evidence": {"process"}}},
        })
        counts = {category: 0 for category in CATEGORIES}
        real = [entry for entry in output.selected if not entry.candidate.demo]
        for _, entry in zip(output.published, real):
            counts[entry.assessment.category] += 1
        document.update(
            publication_count=len(output.published), publication_counts=counts,
            short_term_interest_changes=[],
        )
    print(json.dumps(document, ensure_ascii=False, indent=2, default=str))


@trace_call("command", "run")
async def run(application: Application, options: argparse.Namespace) -> None:
    """Start the selected task once and await its durable output.

    Args:
        application: Composed runtime and registered task implementations.
        options: Selected task name and optional source page.
    """
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    handle = await DBOS.start_workflow_async(application.tasks.dispatch, options.job, day, options.page)
    logger.info(
        'Manual task submitted: job=%s.',
        options.job,
        extra={"details": {'workflow': handle.workflow_id}},
    )
    output = await handle.get_result()
    display(output)
