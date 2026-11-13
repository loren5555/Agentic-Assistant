"""Submit and inspect tasks without opening DBOS, providers or SQLite.

Input origin: CLI command arguments and local service settings.
Output destination: loopback HTTP requests and completed JSON business reports.
Responsibility: bound each HTTP request, poll long jobs, and leave accepted work
running when the caller disconnects. Request IDs make uncertain submissions retryable.
"""

import asyncio

import httpx

from assistant.runtime.service.models import (
    RUNTIME_HEADER,
    TERMINAL_STATES,
    runtime_identity,
)
from logger import get_logger


class ServiceClient:
    """Access the configured runtime through the local execution service."""

    def __init__(self, settings) -> None:
        """Select a loopback port and the expected runtime data directory."""
        self.url = f"http://127.0.0.1:{settings.runtime.service.port}"
        self.http = httpx.AsyncClient(
            base_url=self.url,
            timeout=15,
            trust_env=False,
            headers={RUNTIME_HEADER: runtime_identity(settings.runtime.directory)},
        )

    async def __aenter__(self):
        """Open the reusable HTTP connection pool."""
        await self.http.__aenter__()
        return self

    async def __aexit__(self, *args):
        """Close client connections without cancelling accepted workflows."""
        await self.http.__aexit__(*args)

    async def request(self, method: str, path: str, **kwargs):
        """Exchange JSON and surface actionable local service errors."""
        try:
            response = await self.http.request(method, path, **kwargs)
        except httpx.ConnectError as error:
            raise RuntimeError(
                f"Cannot reach Assistant at {self.url}. Start `python -m assistant serve` "
                "with the same --config in another terminal."
            ) from error
        except httpx.TimeoutException as error:
            raise RuntimeError(
                "Assistant request timed out. Accepted tasks continue in the service; "
                "use status WORKFLOW_ID or retry with the same --request-id."
            ) from error
        document = response.json()
        if response.is_error:
            raise RuntimeError(
                document.get("error", f"Service returned HTTP {response.status_code}")
            )
        return document

    async def wait(self, workflow_id: str):
        """Poll persisted state and return the same report for direct/detached runs."""
        logger = get_logger("runtime.service.client")
        previous = None
        while True:
            state = await self.request("GET", f"/jobs/{workflow_id}")
            if state["status"] != previous:
                logger.info(
                    "Task state: job=%s status=%s.",
                    state.get("job") or state["name"],
                    state["status"],
                    extra={"details": {"workflow": workflow_id}},
                )
                previous = state["status"]
            if state["status"] in TERMINAL_STATES:
                return await self.request("GET", f"/jobs/{workflow_id}/result")
            await asyncio.sleep(1)
