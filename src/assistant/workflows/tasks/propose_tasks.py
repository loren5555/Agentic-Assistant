"""Submit Inbox, elevated TODO inputs and revised BrainStorm candidates through shared organization and proposal.

Input origin:
    Inbox and TODO processors supply pending inputs. The BrainStorm processor supplies
    candidate revisions reopened by human feedback.
Output destination:
    Workbench receives proposals; sources are acknowledged after publication.
Responsibility:
    Select source roles, not perform execution or handle human feedback.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from dbos import DBOS
from logger import trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows


@DBOS.workflow(name="JobWorkflows.propose_tasks.v2")
@trace_call("workflow", "propose_tasks")
async def propose_tasks(self: TaskWorkflows) -> list[str]:
    """Submit pending human input without executing its proposals.

    Returns:
        Workbench proposal links.
    """
    return await self.intake_sources(["inbox", "todo", "brainstorm"])


@DBOS.step(name="JobWorkflows.lookup.v2")
@trace_call("step", "lookup")
def lookup(self: TaskWorkflows, key: str) -> dict | None:
    """Locate the latest submitted version.

    Args:
        key: Stable source role and page identity.

    Returns:
        Saved business pointer, or None.
    """
    return self.index.get(key)
