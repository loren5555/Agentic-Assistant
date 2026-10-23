"""Execute the status command."""

from __future__ import annotations

from typing import TYPE_CHECKING
import argparse

from dbos import DBOS

from assistant.commands.run import display
from logger import get_logger

if TYPE_CHECKING:
    from assistant.runtime.application import Application


async def run(application: Application, options: argparse.Namespace) -> None:
    """Display persisted schedules and recent workflow statuses.

    Args:
        application: Configured application runtime.
        options: Parsed command arguments.
    """
    logger = get_logger("commands.status")
    schedules = await DBOS.list_schedules_async()
    workflows = await DBOS.list_workflows_async(
        limit=20, sort_desc=True, load_input=False, load_output=False,
    )
    logger.info("Runtime status loaded: schedules=%d recent_workflows=%d.", len(schedules), len(workflows))
    display({"schedules": schedules, "workflows": [
        {"id": item.workflow_id, "status": item.status, "name": item.name}
        for item in workflows
    ]})
