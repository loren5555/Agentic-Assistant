"""Delegated work, its optional plan and its results."""

from typing import Literal

from pydantic import BaseModel, Field

from .context import ContextNote
from .input import SourceReference, WorkInput
from .knowledge import KnowledgeNote


class ExecutionPlan(BaseModel):
    """Describe the intended steps handed to an executor."""

    title: str
    content: str
    sources: list[SourceReference]
    simulated: bool = True


class WorkRequest(BaseModel):
    """Delegate work, optionally with a plan prepared by another capability."""

    input: WorkInput
    context: list[str]
    plan: ExecutionPlan | None = None


class WorkResult(BaseModel):
    status: Literal["completed", "needs_input"]
    summary: str
    plan: ExecutionPlan | None = None
    knowledge_notes: list[KnowledgeNote] = Field(default_factory=list)
    context_notes: list[ContextNote] = Field(default_factory=list)
    question: str | None = None
