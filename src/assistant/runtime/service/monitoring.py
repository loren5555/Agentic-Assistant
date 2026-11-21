"""Present saved DBOS runs to the browser without executing business work.

Input: panel filters and execution IDs. Output: paginated summaries and saved
inputs, results, checkpoints and relationships. Payloads are loaded only when a
run is opened; metadata queries stay in the read-only SQLite adapter.
"""

import asyncio
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from dbos import DBOS
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.routing import Route

from logger import get_logger

from .metadata import RunFilters

logger = get_logger("runtime.service.monitoring")


def document(value):
    """Convert saved typed values into inspectable JSON, never rendered HTML."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return document(asdict(value))
    if isinstance(value, dict):
        return {str(key): document(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [document(item) for item in value]
    if isinstance(value, (date, datetime, Path, Enum)):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def routes(application, metadata, respond):
    """Bind observation endpoints to one already-running DBOS instance."""

    async def runs(request):
        filters = RunFilters.model_validate(dict(request.query_params))
        logger.debug(
            "Reading panel execution summaries: page=%d scope=%s.",
            filters.page,
            filters.scope,
        )
        result = await asyncio.to_thread(metadata.list_runs, filters)
        logger.debug(
            "Panel execution summaries read: returned=%d total=%d.",
            len(result["items"]),
            result["total"],
        )
        return respond(result)

    async def detail(request):
        workflow_id = request.path_params["workflow_id"]
        logger.debug(
            "Reading saved panel execution details.",
            extra={"details": {"workflow": workflow_id}},
        )
        summary = await asyncio.to_thread(metadata.get, workflow_id)
        if not summary:
            raise HTTPException(404, "Workflow not found")
        saved = await DBOS.get_workflow_status_async(workflow_id)
        if not saved:
            raise HTTPException(404, "Workflow no longer exists")
        steps = await DBOS.list_workflow_steps_async(workflow_id)
        references = await asyncio.to_thread(metadata.references, workflow_id)
        logger.debug(
            "Saved execution details read: title=%r steps=%d.",
            summary["title"],
            len(steps),
        )
        return respond(
            {
                "run": summary,
                "input": document(saved.input),
                "output": document(saved.output),
                "error": str(saved.error) if saved.error else None,
                "steps": document(steps),
                "references": references,
            }
        )

    async def overview(request):
        return respond(
            {
                "recent": await asyncio.to_thread(
                    metadata.list_runs, RunFilters(since="24h", page_size=6)
                ),
                "states": (
                    await asyncio.to_thread(
                        metadata.list_runs, RunFilters(since="all", page_size=1)
                    )
                )["counts"],
                "schedules": document(await DBOS.list_schedules_async()),
                "queues": await asyncio.to_thread(metadata.queues),
            }
        )

    return [
        Route("/panel/runs", runs),
        Route("/panel/overview", overview),
        Route("/panel/runs/{workflow_id}", detail),
    ]
