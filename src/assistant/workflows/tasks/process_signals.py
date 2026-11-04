"""Bring explicit paper/feed follow-ups and interest requests into normal intake.

Input origin:
    Registered Paper, Feed and Interest processors, each with its own queue rule.
Output destination:
    Shared Organizer/Proposer submit Workbench proposals, without Inbox copies.
Responsibility:
    Interested marks personalize the newspaper. Only Follow Up checkboxes request
    proposal work; ordinary reading feedback never creates Workbench load.
"""

from dbos import DBOS
from logger import trace_call


@DBOS.workflow(name="JobWorkflows.process_signals.v2")
@trace_call("workflow", "process_signals")
async def process_signals(self) -> list[str]:
    """Submit explicit interest signals as ordinary source versions.

    Returns:
        Proposal links awaiting human review.
    """
    return await self.intake_sources(["paper", "feed", "interest"])
