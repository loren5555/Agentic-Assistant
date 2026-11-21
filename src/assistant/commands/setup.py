"""Prepare assistant-owned source context and output publication properties.

Input origin:
    Explicit setup command and configured storage plugins.
Output destination:
    Additive schema changes in source databases, Workbench and output collections.
Responsibility:
    Prepare version/feedback/history flags, terminal work states and publication
    keys under the exclusive runtime lock, with serve stopped. DBOS is not
    launched; no task is recovered, proposed, approved or executed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import argparse
import asyncio

from assistant.runtime.services import Services
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import Application


def initialize_schema(services: Services, topics: list[str]) -> None:
    """Initialize only the Notion additions used by these workflows.

    Args:
        services: Configured storage providers.
    """
    logger = get_logger("main")
    logger.info("Initializing Workbench lifecycle, Selected Action, proposal versions and publication keys.")
    services.workbench.initialize_schema()
    logger.info("Initializing accepted output publication schema.")
    services.publisher.initialize_schema()
    services.discovery_pool.initialize_schema()
    services.feed.initialize_schema()
    services.recommendation_tags.initialize(services.discovery_pool.data_source_id(), topics)
    for kind in ("inbox", "todo", "notero", "simpread", "paper", "feed", "interest"):
        logger.info("Initializing source context schema: source=%s.", kind)
        services.processor(kind).initialize_schema()


@trace_call("command", "setup")
async def run(application: Application, options: argparse.Namespace) -> None:
    """Initialize the configured Notion collections.

    Args:
        application: Runtime exposing lazy storage capabilities.
        options: Parsed setup command arguments.
    """
    requested = getattr(options, "recommendation_topics", None) or []
    topics = list(dict.fromkeys(topic.strip() for topic in requested if topic.strip()))
    await asyncio.to_thread(initialize_schema, application.services, topics)
    get_logger("commands.setup").info(
        "Setup complete. Add your research directions in Notion under Assistant → Recommendation Tags."
    )
