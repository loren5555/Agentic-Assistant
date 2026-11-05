"""Planning service available to the approved-action dispatcher."""

from typing import Protocol

from assistant.components.execution.task_worker.models import TaskRequest, TaskResult


class PlannerProtocol(Protocol):
    """Develop a concrete plan within the approved planning scope."""

    async def execute(self, task: TaskRequest) -> TaskResult:
        """Return a plan or focused questions for human review.

        Args:
            task: Approved planning proposal and effective source context.

        Returns:
            Structured plan and report, or questions requiring human input.
        """
        ...
