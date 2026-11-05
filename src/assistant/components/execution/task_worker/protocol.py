"""Capability interfaces for task worker."""

from typing import Protocol

from assistant.components.execution.task_worker.models import TaskRequest
from assistant.components.execution.task_worker.models import TaskResult


class TaskWorkerProtocol(Protocol):
    """Complete supplied work without managing external workflow records."""

    async def execute(self, task: TaskRequest) -> TaskResult:
        """Produce the deliverable defined by an approved task.

        Args:
            task: Approved scope and current human instructions.

        Returns:
            The actual completed result.
        """
        ...
