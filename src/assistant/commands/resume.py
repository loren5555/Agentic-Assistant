"""Recover a named existing workflow instead of submitting a new business task.

Inputs:
    An existing workflow ID from status and an Application with the corresponding
    durable functions registered against the selected runtime database.

Outputs:
    The recovered workflow's actual result as JSON, or an exception explaining
    why recovery or execution could not complete.

Workflow relationship:
    runtime/recovery.recover rewinds an ERROR workflow from its failed step,
    retaining earlier successful checkpoints, or requests DBOS resumption for
    interrupted work. Incomplete work from another application version is
    rejected explicitly rather than migrated or silently left waiting.

Participants and effects:
    Human operator, recovery helper, DBOS, and the original task's plugins.
    Unfinished steps may call models and write external records. This command
    neither deletes old tasks nor replaces required human approval.
"""

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
