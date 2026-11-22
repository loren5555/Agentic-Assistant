"""Grounded understanding shared by all information sources."""

from pydantic import BaseModel


class OrganizedInformation(BaseModel):
    """Explain useful material without performing the proposed task.

    Attributes:
        worth_archiving: Existing evidence supports a reusable reading product.
        worth_proposing: Follow-up work or a human decision is needed.
        understanding: Interpretation of the supplied material and intent.
        key_points: Grounded findings worth considering.
        possible_outputs: Suitable knowledge, paper, idea, interest or task outcomes.
        limitations: Missing evidence and inferred rather than explicit interests.
    """

    worth_archiving: bool = False
    worth_proposing: bool = True
    understanding: str
    key_points: list[str]
    possible_outputs: list[str]
    limitations: list[str]
