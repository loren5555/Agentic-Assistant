"""The provider interface for recalling and retaining working context."""

from typing import Protocol

from assistant.schemas.execution import WorkResult
from assistant.schemas.input import WorkInput


class ContextStoreProtocol(Protocol):
    def search(self, input: WorkInput) -> list[str]: ...

    def remember(self, input: WorkInput, result: WorkResult) -> None: ...
