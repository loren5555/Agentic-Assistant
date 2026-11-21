"""Expose durable execution to local CLI clients and the browser task panel.

Input origin:
    Loopback HTTP requests with the selected runtime directory header.
Output destination:
    DBOS queues for submissions; JSON state/results/steps for observers.
Responsibility:
    Acknowledge only persisted submissions, keep execution independent of HTTP,
    and query saved state without reading Notion or invoking business components.
"""

import asyncio
import json
from pathlib import Path

from dbos import DBOS, SetWorkflowID
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, FileResponse
from starlette.staticfiles import StaticFiles
from starlette.routing import Route, Mount
import uvicorn

from assistant.runtime.service import administration, monitoring, scheduling
from assistant.runtime.service.metadata import RunMetadata, JOB_LABELS
from assistant.runtime.recovery import check_version
from assistant.runtime.service.models import (
    JobSubmission,
    RecoverySubmission,
    RUNTIME_HEADER,
    runtime_identity,
)
from assistant.runtime.service.presentation import error_message, result_document
from assistant.runtime.service.submissions import (
    RECOVERY_QUEUE,
    recover_requested_workflow,
    submit_job,
)
from logger import get_logger, call_scope

logger = get_logger("runtime.service.server")


class LocalServer(uvicorn.Server):
    """Finish HTTP shutdown before Application gives DBOS its shutdown window."""

    def handle_exit(self, sig, frame) -> None:
        """Consume shutdown signals here instead of replaying them during DBOS cleanup."""
        self.should_exit = True


def json_response(document, status_code=200):
    """Serialize dates and saved step values using the CLI's JSON convention."""
    return JSONResponse(
        json.loads(json.dumps(document, ensure_ascii=False, default=str)),
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def workflow_document(state):
    """Present saved execution metadata without loading business outputs."""
    attributes = state.attributes or {}
    return {
        "id": state.workflow_id,
        "status": state.status,
        "name": state.name,
        "job": attributes.get("job"),
        "page": attributes.get("page"),
        "parent_id": state.parent_workflow_id,
        "queue": state.queue_name,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "completed_at": state.completed_at,
        "application_version": state.app_version,
    }


def create_app(application):
    """Bind HTTP handlers to the already-launched local execution environment."""
    identity = runtime_identity(application.settings.runtime.directory)
    # HTTP mutation requests share this event loop. One lock makes duplicate
    # request checks and enqueue operations atomic with respect to other clients.
    submissions = asyncio.Lock()
    metadata = RunMetadata(application.settings.runtime.directory)
    web = Path(__file__).with_name("web")

    async def panel(request):
        return FileResponse(web / "index.html", headers={"Cache-Control": "no-cache"})

    async def bootstrap(request):
        return json_response(
            {
                "runtime": identity,
                "application_version": DBOS.application_version,
                "jobs": JOB_LABELS,
                "status": "ready",
            }
        )

    async def require_state(workflow_id):
        """Read one workflow's metadata, returning 404 for unknown IDs."""
        rows = await DBOS.list_workflows_async(
            workflow_ids=[workflow_id],
            limit=1,
            load_input=False,
            load_output=False,
        )
        if not rows:
            raise HTTPException(404, "Workflow not found")
        return rows[0]

    async def health(request: Request):
        """Identify the running service without touching a business provider."""
        return json_response(
            {
                "status": "ready",
                "runtime_directory": identity,
                "application_version": DBOS.application_version,
            }
        )

    async def submit(request: Request):
        """Persist a validated task and return immediately with its stable ID."""
        submission = JobSubmission.model_validate(await request.json())
        logger.info("Task submission received: job=%s.", submission.job)
        async with submissions:
            workflow_id = await submit_job(application, submission)
        return json_response({"id": workflow_id, "job": submission.job}, 202)

    async def status(request: Request):
        """List persisted workflows and schedules for the configured service."""
        limit = int(request.query_params.get("limit", 20))
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        logger.debug("Reading service status: limit=%d.", limit)
        rows = await DBOS.list_workflows_async(
            limit=limit, sort_desc=True, load_input=False, load_output=False
        )
        schedules = await DBOS.list_schedules_async()
        logger.debug(
            "Service status read: workflows=%d schedules=%d.", len(rows), len(schedules)
        )
        return json_response(
            {
                "service": {"status": "ready", "runtime_directory": identity},
                "schedules": schedules,
                "workflows": [workflow_document(row) for row in rows],
            }
        )

    async def state(request: Request):
        """Read one saved workflow state without awaiting its completion."""
        return json_response(
            workflow_document(await require_state(request.path_params["workflow_id"]))
        )

    async def steps(request: Request):
        """Inspect checkpoints and child workflow references for one execution."""
        workflow_id = request.path_params["workflow_id"]
        await require_state(workflow_id)
        return json_response(
            {
                "id": workflow_id,
                "steps": await DBOS.list_workflow_steps_async(workflow_id),
            }
        )

    async def result(request: Request):
        """Return the saved result/error; polling never reruns the workflow."""
        workflow_id = request.path_params["workflow_id"]
        await require_state(workflow_id)
        saved = await DBOS.get_workflow_status_async(workflow_id)
        if saved.status == "SUCCESS":
            return json_response(
                {
                    "id": workflow_id,
                    "status": saved.status,
                    "result": result_document(saved.output),
                }
            )
        if saved.status in {"ERROR", "CANCELLED", "MAX_RECOVERY_ATTEMPTS_EXCEEDED"}:
            return json_response(
                {
                    "id": workflow_id,
                    "status": saved.status,
                    "error": error_message(saved.error, saved.status),
                }
            )
        return json_response({"id": workflow_id, "status": saved.status}, 202)

    async def schedules(request: Request):
        """Read registered schedules independently of the workflow list."""
        return json_response({"schedules": await DBOS.list_schedules_async()})

    async def resume(request: Request):
        """Persist recovery as a durable control task rather than an HTTP wait."""
        workflow_id = request.path_params["workflow_id"]
        submission = RecoverySubmission.model_validate(await request.json())
        recovery_id = f"recovery:{submission.request_id}"
        async with submissions:
            original = await require_state(workflow_id)
            check_version(original)
            if original.status in {"SUCCESS", "PENDING", "ENQUEUED", "DELAYED"}:
                return json_response({"id": workflow_id, "target_id": workflow_id}, 202)
            existing = await DBOS.get_workflow_status_async(recovery_id)
            if existing and existing.input["args"][0] != workflow_id:
                raise ValueError("Request ID already belongs to another recovery")
            if not existing:
                with SetWorkflowID(recovery_id):
                    await DBOS.enqueue_workflow_async(
                        RECOVERY_QUEUE, recover_requested_workflow, workflow_id
                    )
        logger.info(
            "Workflow recovery queued.",
            extra={"details": {"workflow": workflow_id, "request": recovery_id}},
        )
        return json_response({"id": recovery_id, "target_id": workflow_id}, 202)

    async def http_error(request, error):
        """Return a short structured error for expected request failures."""
        return json_response({"error": str(error.detail)}, error.status_code)

    app = Starlette(
        routes=[
            Route("/", panel),
            Route("/panel/bootstrap", bootstrap),
            Mount("/assets", StaticFiles(directory=web), name="panel-assets"),
            *monitoring.routes(application, metadata, json_response),
            *scheduling.routes(application.schedule_manager, json_response),
            *administration.routes(metadata, json_response, submissions),
            Route("/health", health),
            Route("/jobs", submit, methods=["POST"]),
            Route("/status", status),
            Route("/schedules", schedules),
            Route("/jobs/{workflow_id}/result", result),
            Route("/jobs/{workflow_id}/steps", steps),
            Route("/jobs/{workflow_id}", state),
            Route("/workflows/{workflow_id}/resume", resume, methods=["POST"]),
        ],
        exception_handlers={HTTPException: http_error},
    )

    async def request_boundary(request, call_next):
        """Reject wrong-runtime requests and report API errors at their boundary."""
        public_read = request.method in {"GET", "HEAD"} and (
            request.url.path in {"/", "/panel/bootstrap"}
            or request.url.path.startswith("/assets/")
        )
        if not public_read and request.headers.get(RUNTIME_HEADER) != identity:
            return json_response(
                {
                    "error": "Runtime mismatch. Use the same --config/runtime.directory as serve."
                },
                409,
            )
        try:
            with call_scope("service", "request"):
                return await call_next(request)
        except (ValidationError, ValueError) as error:
            return json_response({"error": str(error)}, 422)
        except Exception as error:
            logger.exception(
                "Local service request failed: method=%s path=%s.",
                request.method,
                request.url.path,
            )
            return json_response({"error": str(error)}, 500)

    app.add_middleware(BaseHTTPMiddleware, dispatch=request_boundary)
    return app


async def serve_http(application):
    """Run the loopback endpoint until Ctrl+C, then let Application close DBOS."""
    port = application.settings.runtime.service.port
    server = LocalServer(
        uvicorn.Config(
            create_app(application),
            host="127.0.0.1",
            port=port,
            access_log=False,
            log_config=None,
            log_level="warning",
            timeout_graceful_shutdown=5,
        )
    )
    logger.info(
        "Local service starting: http://127.0.0.1:%d. Ready for the browser panel and run/status/resume requests.",
        port,
    )
    await server.serve()
    logger.info("Local service stopped accepting requests.")
