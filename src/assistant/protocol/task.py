"""Interfaces for completing approved work and managing its execution cycle."""

from typing import Protocol

from assistant.schemas.proposal import ProposedTask
from assistant.schemas.task import ExecutionCycle, TaskResult


class TaskWorkerProtocol(Protocol):
    """Complete supplied work without managing external workflow records."""

    async def execute(self, task: ProposedTask) -> TaskResult:
        """Produce the deliverable defined by an approved task.

        Args:
            task: Approved scope and current human instructions.

        Returns:
            The actual completed result.
        """
        ...


class TaskRunnerProtocol(Protocol):
    """Own routing, execution, and writeback for approved Workbench proposals."""

    async def run_cycle(self) -> ExecutionCycle:
        """Execute one eligible proposal from persistent storage.

        Returns:
            Saved execution, clarification, or failure information.
        """
        ...
