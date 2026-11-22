"""Keep the runtime alive and trigger explicitly configured recurring tasks.

Input origin:
    YAML runtime.schedules is supplied by Application. DBOS persists the schedule
    definitions and later supplies scheduled_time/context to scheduled_job in
    runtime/schedules.py; that trigger enqueues workflows/tasks/dispatch.py.

Output destination:
    Schedule definitions and entry jobs go to DBOS. Each triggered job enters the
    same tasks used by manual run, and writes the destinations described by that
    task. Serve itself reports progress through logs rather than stdout reports.

Inputs:
    Application settings with runtime.schedules: job names mapped to cron
    expressions or records with cron/timezone/enabled. Browser edits are saved
    back to this YAML and synchronized online with the existing DBOS database.

Outputs:
    Persisted schedules, local HTTP submission/inspection endpoints and execution
    logs. This command owns the executor until interrupted.

Workflow relationship:
    runtime/schedules.scheduled_job receives the scheduled time and stored job
    context, then calls the same run.dispatch workflow used by manual execution.
    The assistant-triggers queue runs schedule callbacks. Both manual and scheduled
    dispatch enter assistant-jobs with worker_concurrency=1; triggers wait outside
    that queue so they never occupy the slot needed by their submitted job.

Participants and effects:
    DBOS scheduler, job queue, dispatcher, and configured business tasks. This
    command removes assistant-owned schedules removed from YAML and applies the
    configured definitions. Automatic backfill is disabled; an empty mapping
    enables no recurring tasks, though unfinished work can still recover.

Boundaries:
    Frequency belongs here; proposal, review, research, and archival policy remain
    in task workflows. A timer never supplies human approval.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import argparse

from dbos import DBOS

from assistant.workflows.steps.review_memory import MEMORY_QUEUE
from assistant.runtime.service.server import serve_http
from assistant.runtime.service.submissions import (
    JOB_QUEUE,
    TRIGGER_QUEUE,
    RECOVERY_QUEUE,
)
from logger import trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import Application


@trace_call("command", "serve")
async def run(application: Application, options: argparse.Namespace) -> None:
    """Apply enabled schedules and serve until interrupted.

    Args:
        application: Configured application runtime.
        options: Parsed command arguments.
    """
    await DBOS.register_queue_async(MEMORY_QUEUE, worker_concurrency=1)
    await DBOS.register_queue_async(JOB_QUEUE, worker_concurrency=1)
    await DBOS.register_queue_async(TRIGGER_QUEUE, worker_concurrency=1)
    await DBOS.register_queue_async(RECOVERY_QUEUE, worker_concurrency=1)
    from assistant.runtime.service.scheduling import ScheduleManager

    application.schedule_manager = ScheduleManager(application.settings)
    await application.schedule_manager.sync()
    await serve_http(application)
