"""Prepare assistant-owned source context and output publication properties.

Input origin:
    Explicit setup command and configured storage plugins.
Output destination:
    Additive schema changes in source databases, Workbench and output collections.
Responsibility:
    Prepare version/feedback/history flags, terminal work states and publication
    keys. No task is proposed, approved or executed by this command itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import argparse
import asyncio
import json
from pathlib import Path

from assistant.runtime.services import Services
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import Application


def initialize_schema(services: Services) -> None:
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
    await asyncio.to_thread(initialize_schema, application.services)
    topics = getattr(options, "recommendation_topics", None)
    if topics:
        topics = list(dict.fromkeys(topic.strip() for topic in topics if topic.strip()))
        path = Path(application.settings.runtime.directory).resolve() / "v2" / "recommendation-topics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8")
        get_logger("commands.setup").info("Initial recommendation topics saved: %s.", ", ".join(topics))
    get_logger("commands.setup").info("Required Notion schema additions initialized.")
