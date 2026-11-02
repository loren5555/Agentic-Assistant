"""Explicitly initialize the storage fields required by current workflows.

Input origin:
    Application supplies storage services and database IDs from YAML to
    initialize_schema(). The command uses those plugins to inspect the existing
    Notion collection schemas, not Inbox or Workbench task contents.

Output destination:
    Schema additions go to Notion Workbench, Papers, Knowledge, Ideas, and Inbox through
    their storage components. Completion/failure goes to the shared log; no
    Proposal, TaskResult, or recommendation is emitted to a business collection.

Inputs:
    Application services selected by YAML and their target collection settings.
    No proposal, source page, or scheduled business job is supplied.

Outputs:
    Initialized schema and progress logs, rather than a task deliverable. Current
    Notion plugins add Workbench Finished, Publication Key, Proposal Version,
    Source Kind, Execution Error, archive publication keys, and the Research
    Feed follow-up identity on Inbox. Papers/Knowledge receive brief receipts.

Workflow relationship:
    Calls initialize_schema on Workbench, ArchiveStore, ResearchFeed, and
    CapturePublisher directly;
    it does not run propose-tasks, reviews, captures, or recommendations itself.

Participants and effects:
    Human operator and storage plugins. Schema changes are explicit here rather
    than repeated on every normal read/write. Application still launches DBOS
    before this handler, so unrelated unfinished workflows may recover at startup.
    This command does not approve or execute new proposals intentionally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import argparse
import asyncio

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
    logger.info("Initializing Workbench lifecycle, Proposal Version, and Publication Key schema.")
    services.workbench.initialize_schema()
    logger.info("Initializing Knowledge/Ideas archive keys.")
    services.archive.initialize_schema()
    logger.info("Initializing Inbox follow-up key.")
    services.feed.initialize_schema()
    logger.info("Initializing Papers/Knowledge brief publication keys.")
    services.capture_publisher.initialize_schema()


@trace_call("command", "setup")
async def run(application: Application, options: argparse.Namespace) -> None:
    """Initialize the configured Notion collections.

    Args:
        application: Runtime exposing lazy storage capabilities.
        options: Parsed setup command arguments.
    """
    await asyncio.to_thread(initialize_schema, application.services)
    get_logger("commands.setup").info("Required Notion schema additions initialized.")
