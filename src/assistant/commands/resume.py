"""Recover an existing durable operation from its failed step."""

from __future__ import annotations

from typing import TYPE_CHECKING
import argparse

from assistant.commands.run import display
from assistant.runtime.recovery import recover
from logger import get_logger

if TYPE_CHECKING:
    from assistant.runtime.application import Application


async def run(application: Application, options: argparse.Namespace) -> None:
    """Recover the requested workflow and display its actual result.

    Args:
        application: Runtime with all durable functions registered.
        options: Existing workflow ID and selected local configuration.
    """
    get_logger("commands.resume").info("Recovering workflow=%s.", options.workflow_id)
    handle = await recover(options.workflow_id)
    output = await handle.get_result()
    display(output)
