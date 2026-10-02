"""The progress and verified results of one triggered task."""

from typing import Literal

from pydantic import BaseModel, Field

from .execution import WorkResult
from .input import WorkInput
from .knowledge import DraftReceipt
from .routing import RouterDecision, Trigger


class WorkRecord(BaseModel):
    """Track a triggered task through verified delivery."""

    trigger: Trigger
    input: WorkInput
    context: list[str]
    decision: RouterDecision | None = None
    status: Literal["running", "completed", "needs_input", "failed"] = "running"
    result: WorkResult | None = None
    drafts: list[DraftReceipt] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
