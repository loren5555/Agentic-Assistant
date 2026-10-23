"""Explicitly initialize required storage fields."""

from __future__ import annotations

from typing import TYPE_CHECKING
import argparse
import asyncio

from assistant.runtime.services import Services
from logger import get_logger

if TYPE_CHECKING:
    from assistant.runtime.application import Application


def initialize_schema(services: Services) -> None:
    """Initialize only the Notion additions used by these workflows.

    Args:
        services: Configured storage providers.
    """
    logger = get_logger("main")
    logger.info("Initializing Workbench lifecycle and Publication Key schema.")
    services.workbench.initialize_schema()
    logger.info("Initializing Knowledge/Ideas archive keys.")
    services.archive.initialize_schema()
    logger.info("Initializing Inbox follow-up key.")
    services.feed.initialize_schema()


async def run(application: Application, options: argparse.Namespace) -> None:
    """Initialize the configured Notion collections.

    Args:
        application: Runtime exposing lazy storage capabilities.
        options: Parsed setup command arguments.
    """
    await asyncio.to_thread(initialize_schema, application.services)
    get_logger("commands.setup").info("Required Notion schema additions initialized.")
