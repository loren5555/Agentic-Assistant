"""Grounded understanding shared by all information sources."""

from pydantic import BaseModel


class OrganizedInformation(BaseModel):
    """Explain useful material without performing the proposed task.

    Attributes:
        understanding: Interpretation of the supplied material and intent.
        key_points: Grounded findings worth considering.
        possible_outputs: Suitable knowledge, paper, idea, interest or task outcomes.
        limitations: Missing evidence and inferred rather than explicit interests.
    """

    understanding: str
    key_points: list[str]
    possible_outputs: list[str]
    limitations: list[str]
