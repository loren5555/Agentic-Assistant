"""Reasoning boundary for a skill-guided role-notebook revision."""
from typing import Protocol
from assistant.components.data.memory.models import MemoryRevision, ReviewFeedback, RoleNote


class MemoryReviewerProtocol(Protocol):
    async def review(self, feedback: ReviewFeedback, earlier: list[dict], notes: list[RoleNote],
                     skill: str) -> MemoryRevision: ...
