"""Inspect the running service without starting DBOS or business work.

Input origin: service settings and optional workflow ID from run --detach.
Output destination: saved workflow/schedule metadata or one report on stdout.
Responsibility: query the local service; only serve owns recovery and providers.
"""

import argparse

from assistant.commands.run import display
from assistant.runtime.service.client import ServiceClient
from logger import get_logger, trace_call


@trace_call("command", "status")
async def run(settings, options: argparse.Namespace) -> None:
    """Display service state or inspect one persisted workflow and its steps."""
    logger = get_logger("commands.status")
    logger.debug("Reading local service status.")
    async with ServiceClient(settings) as client:
        if options.workflow_id:
            path = f"/jobs/{options.workflow_id}"
            if options.result:
                output = await client.request("GET", path + "/result")
            else:
                output = await client.request("GET", path)
                output["steps"] = (await client.request("GET", path + "/steps"))["steps"]
        else:
            output = await client.request("GET", "/status", params={"limit": options.limit})
    logger.debug("Local service status read.")
    display(output)
