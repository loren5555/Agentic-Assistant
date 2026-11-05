"""A deterministic source update requested by human feedback."""

from typing import Literal
from pydantic import BaseModel
from assistant.components.data.sources.models import SourceHistory


class Reconciliation(BaseModel):
    """Describe the storage effects of one human decision.

    Attributes:
        status: Terminal state of the old Workbench task.
        feedback: New source supplement, absent when work was rejected.
    """

    status: Literal["Superseded", "Deprecated"]
    feedback: SourceHistory | None = None
