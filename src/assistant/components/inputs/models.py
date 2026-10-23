"""Material submitted for interpretation and proposal drafting."""

from typing import Literal

from pydantic import BaseModel


class SourceMaterial(BaseModel):
    """Describe material submitted by a human.

    Attributes:
        kind: Input database containing this material.
        page_id: Source page identifier.
        url: Source link retained after intake closes.
        title: Original input title.
        text: Meaningful source properties and page content.
        revision: Source edit timestamp at intake.
    """

    kind: Literal["inbox", "todo", "notero", "simpread"]
    page_id: str
    url: str
    title: str
    text: str
    revision: str
