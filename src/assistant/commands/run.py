"""Run one of the five complete tasks and print its result."""

from __future__ import annotations

from datetime import datetime
from time import monotonic
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo
import argparse
import json

from dbos import DBOS
from pydantic import BaseModel

from assistant.components.recommendations.models import CATEGORIES, RecommendationRun
from assistant.runtime.recovery import invoke
from logger import get_logger

logger = get_logger("commands.run")


if TYPE_CHECKING:
    from assistant.runtime.application import Application, TaskWorkflows


@DBOS.workflow(name="JobWorkflows.dispatch")
async def dispatch(self: TaskWorkflows, job: str, day: str, page_id: str | None = None):
    """Run one named job and return its actual outputs.

    Args:
        job: Intake, reviews, papers, articles, or recommendations.
        day: Asia/Shanghai date used for daily recommendation identity.
        page_id: Optional raw capture for manual reprocessing.

    Returns:
        Job links or an evidence-grounded recommendation report.
    """
    started = monotonic()
    logger.info("Job started: job=%s workflow=%s day=%s page=%s.", job, DBOS.workflow_id, day, page_id or "batch")
    try:
        if job == "intake":
            output = await self.process_inputs()
        elif job == "reviews":
            output = await self.process_reviews()
        elif job == "papers":
            output = await self.organize_papers(page_id)
        elif job == "articles":
            output = await self.organize_articles(page_id)
        elif job == "recommendations":
            mode = "demo" if self.services.config.providers.discovery == "demo" else "real"
            output = await invoke(f"recommendations:{mode}:{day}", self.research.recommend_papers, day)
            logger.info("Recommendation result: demo=%s selected=%d published=%d rejected=%d source_failures=%d pending_recovery=%d.",
                        output.demo, len(output.selected), len(output.published), len(output.rejected),
                        len(output.source_failures), len(output.pending_recovery))
        else:
            raise ValueError(f"Unknown job: {job}")
    except Exception:
        logger.exception("Job failed: job=%s workflow=%s elapsed=%.2fs.", job, DBOS.workflow_id, monotonic() - started)
        raise
    logger.info("Job completed: job=%s workflow=%s elapsed=%.2fs.", job, DBOS.workflow_id, monotonic() - started)
    return output


def display(output) -> None:
    """Print business outputs without exposing configuration or model credentials.

    Args:
        output: Workflow report or collection of verified destination links.
    """
    document = output.model_dump(mode="json") if isinstance(output, BaseModel) else output
    if isinstance(output, RecommendationRun):
        counts = {category: 0 for category in CATEGORIES}
        real = [entry for entry in output.selected if not entry.candidate.demo]
        for _, entry in zip(output.published, real):
            counts[entry.assessment.category] += 1
        document.update(
            publication_count=len(output.published), publication_counts=counts,
            short_term_interest_changes=[],
        )
    print(json.dumps(document, ensure_ascii=False, indent=2, default=str))


async def run(application: Application, options: argparse.Namespace) -> None:
    """Start the selected task once and await its durable output.

    Args:
        application: Composed runtime and registered task implementations.
        options: Selected task name and optional source page.
    """
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    handle = await DBOS.start_workflow_async(application.tasks.dispatch, options.job, day, options.page)
    logger.info("Manual task submitted: job=%s workflow=%s.", options.job, handle.workflow_id)
    output = await handle.get_result()
    display(output)
