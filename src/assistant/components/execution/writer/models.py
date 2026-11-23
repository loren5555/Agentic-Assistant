"""The publishable manuscript returned to a workflow, separate from its assignment."""
from typing import Literal
from pydantic import BaseModel, Field
from assistant.components.execution.briefer.models import PaperReadingMetadata


class Manuscript(BaseModel):
    """Supply the body, catalog summary and evidence scope used by Publisher."""

    content: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence_level: Literal["full_text", "abstract", "notes", "metadata"]
    reading: PaperReadingMetadata | None = None
