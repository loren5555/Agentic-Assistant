"""Reasoning boundary for revising role notebooks using project instructions."""
from typing import Protocol
from assistant.components.data.memory.models import MemoryRevision, ReviewFeedback, RoleNote


class MemoryReviewerProtocol(Protocol):
    async def review(self, feedback: ReviewFeedback, earlier: list[dict], notes: list[RoleNote],
                     instructions: str) -> MemoryRevision: ...
