"""The provider interface for executing delegated work."""

from typing import Protocol

from assistant.schemas.execution import WorkRequest, WorkResult


class ExecutorProtocol(Protocol):
    async def execute(self, request: WorkRequest) -> WorkResult: ...
