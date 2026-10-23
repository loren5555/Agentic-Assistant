"""Execute the serve command."""

from __future__ import annotations

from typing import TYPE_CHECKING
import argparse
import asyncio

from dbos import DBOS

from assistant.runtime import schedules
from logger import get_logger

if TYPE_CHECKING:
    from assistant.runtime.application import Application


async def run(application: Application, options: argparse.Namespace) -> None:
    """Apply enabled schedules and serve until interrupted.

    Args:
        application: Configured application runtime.
        options: Parsed command arguments.
    """
    logger = get_logger("commands.serve")
    await DBOS.register_queue_async("assistant-jobs", worker_concurrency=1)
    enabled = application.settings.runtime.schedules
    for schedule in await DBOS.list_schedules_async():
        name = schedule["schedule_name"]
        if name.startswith("assistant-") and name.removeprefix("assistant-") not in enabled:
            await asyncio.to_thread(DBOS.pause_schedule, name)
            logger.info("Paused schedule removed from configuration: name=%s.", name)
    definitions = [
        {
            "schedule_name": "assistant-" + job, "workflow_fn": schedules.scheduled_job,
            "schedule": cron, "cron_timezone": "Asia/Shanghai",
            "context": {"job": job}, "automatic_backfill": False,
            "queue_name": "assistant-jobs",
        }
        for job, cron in enabled.items()
    ]
    await DBOS.apply_schedules_async(definitions)
    logger.info("Scheduler ready: schedules=%d timezone=Asia/Shanghai backfill=False. Ctrl+C to stop.", len(enabled))
    for job, cron in enabled.items():
        logger.info("Schedule enabled: job=%s cron=%s.", job, cron)
    await asyncio.Event().wait()
