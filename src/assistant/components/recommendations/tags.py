"""Shared reading vocabulary for newspaper candidates and retained papers.

Readers see the same Notion catalog. Their proposed matches become relations only
when the item is saved. Publishing or classifying a paper contributes no votes.
"""

from pydantic import BaseModel, Field


class DirectionTag(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    definition: str = Field(max_length=600)
    existing_id: str = ""


TAG_INSTRUCTIONS = """
Classify the supplied reading into zero to three durable research directions.
For an applicable catalog entry use its exact existing_id and name, including
when the source uses a synonym. Consider paused entries when matching subjects.
For an uncovered direction supply a concise name, a reusable scope definition
and an empty existing_id. Methods, datasets and author keywords remain searchable
keywords. If the available text gives no reliable direction, return an empty list.
"""
