"""Keep the runtime alive and trigger explicitly configured recurring tasks.

Input origin:
    YAML runtime.schedules is supplied by Application. DBOS persists the schedule
    definitions and later supplies scheduled_time/context to scheduled_job in
    runtime/schedules.py; that trigger calls commands/run.dispatch.

Output destination:
    Schedule definitions and entry jobs go to DBOS. Each triggered job enters the
    same tasks used by manual run, and writes the destinations described by that
    task. Serve itself reports progress through logs rather than stdout reports.

Inputs:
    Application settings with runtime.schedules: job names mapped to cron
    expressions. Schedules use Asia/Shanghai and the existing DBOS database.

Outputs:
    Persisted schedule definitions and progress logs; this command waits until
    interrupted rather than returning one business result as JSON.

Workflow relationship:
    runtime/schedules.scheduled_job receives the scheduled time and stored job
    context, then calls the same run.dispatch workflow used by manual execution.
    The assistant-jobs queue serializes entry dispatch with worker_concurrency=1.

Participants and effects:
    DBOS scheduler, job queue, dispatcher, and configured business tasks. This
    command pauses assistant-owned schedules removed from YAML and applies the
    configured definitions. Automatic backfill is disabled; an empty mapping
    enables no recurring tasks, though unfinished work can still recover.

Boundaries:
    Frequency belongs here; proposal, review, research, and archival policy remain
    in task workflows. A timer never supplies human approval.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import argparse
import asyncio

from dbos import DBOS

from assistant.runtime import schedules
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import Application


@trace_call("command", "serve")
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
