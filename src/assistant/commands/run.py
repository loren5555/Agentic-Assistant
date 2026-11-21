"""Submit one business job to the running local service and display its result.

Input origin: run JOB arguments and the selected service configuration.
Output destination: a durable DBOS request via HTTP, then JSON on stdout.
Responsibility: the client submits/waits; serve owns providers and execution.
Ctrl+C stops waiting while accepted work continues. --detach returns its ID.
"""

import argparse
import json

from assistant.runtime.service.client import ServiceClient
from assistant.runtime.service.models import JobSubmission
from logger import get_logger, trace_call


def display(output) -> None:
    """Print a service response or business report as readable JSON."""
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


async def display_completion(client: ServiceClient, workflow_id: str) -> None:
    """Wait for the durable result and retain useful failure context."""
    document = await client.wait(workflow_id)
    if document["status"] != "SUCCESS":
        raise RuntimeError(f"Task {workflow_id} ended with {document['status']}: {document.get('error', '')}")
    display(document["result"])


@trace_call("command", "run")
async def run(settings, options: argparse.Namespace) -> None:
    """Submit one idempotent request and optionally wait for the saved result."""
    values = {"job": options.job, "page": options.page}
    if getattr(options, "refresh", False):
        values["refresh"] = True
    if options.request_id:
        values["request_id"] = options.request_id
    submission = JobSubmission.model_validate(values)
    logger = get_logger("commands.run")
    # Print the ID before network I/O so an uncertain POST can be retried safely.
    logger.info("Submitting task: job=%s request_id=%s.", options.job, submission.request_id)
    async with ServiceClient(settings) as client:
        receipt = await client.request("POST", "/jobs", json=submission.model_dump(mode="json"))
        logger.info("Task accepted: job=%s workflow=%s. Ctrl+C stops waiting; service execution continues.",
                    options.job, receipt["id"])
        if options.detach:
            display(receipt)
        else:
            await display_completion(client, receipt["id"])
