"""Request durable recovery from the service without becoming an executor.

Input origin: an existing workflow ID and the same configuration as serve.
Output destination: a recovery receipt or the recovered business result on stdout.
Responsibility: serve applies existing version checks and failed-step recovery;
HTTP client lifetime does not control the accepted recovery operation.
"""

import argparse

from assistant.commands.run import display, display_completion
from assistant.runtime.service.client import ServiceClient
from assistant.runtime.service.models import RecoverySubmission
from logger import get_logger, trace_call


@trace_call("command", "resume")
async def run(settings, options: argparse.Namespace) -> None:
    """Submit a recover request, or watch work that is already active/completed."""
    submission = RecoverySubmission(request_id=options.request_id) if options.request_id else RecoverySubmission()
    get_logger("commands.resume").info("Requesting recovery: workflow=%s request_id=%s.", options.workflow_id, submission.request_id)
    async with ServiceClient(settings) as client:
        receipt = await client.request("POST", f"/workflows/{options.workflow_id}/resume",
                                       json=submission.model_dump(mode="json"))
        if options.detach:
            display(receipt)
        else:
            await display_completion(client, receipt["id"])
