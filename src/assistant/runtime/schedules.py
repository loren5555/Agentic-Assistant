"""Bind persisted schedule triggers to the same tasks used by manual runs."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from dbos import DBOS

from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import Application

SHANGHAI = ZoneInfo("Asia/Shanghai")
_application: Application | None = None
_serving = False


def bind(application: Application, *, serving: bool) -> None:
    """Supply the live runtime before DBOS starts recovering schedule triggers.

    Args:
        application: Registered task implementations and configuration.
        serving: Whether this process may dispatch recurring work.
    """
    global _application, _serving
    _application = application
    _serving = serving


@DBOS.workflow(name="scheduled_job")
@trace_call("workflow", "scheduled_job")
async def scheduled_job(scheduled_time: datetime, context: dict[str, str]):
    """Dispatch an explicitly enabled schedule through the configured application.

    Args:
        scheduled_time: DBOS-supplied scheduled instant.
        context: Persisted job name, without credentials or provider objects.

    Returns:
        Job output, or None when the application was launched in manual mode.
    """
    if not _serving or context["job"] not in _application.tasks.settings.schedules:
        return None
    get_logger("main").info("Scheduled job triggered: job=%s scheduled_time=%s workflow=%s.",
                            context["job"], scheduled_time.isoformat(), DBOS.workflow_id)
    day = scheduled_time.astimezone(SHANGHAI).date().isoformat()
    output = await _application.tasks.dispatch(context["job"], day)
    return output
