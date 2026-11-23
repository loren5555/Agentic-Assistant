"""Grounded understanding shared by all information sources."""

from pydantic import BaseModel, Field, model_validator
from pydantic.json_schema import SkipJsonSchema


class FollowUp(BaseModel):
    """One outstanding request and the evidence that makes it relevant now."""

    work: str = Field(min_length=1)
    basis: str = Field(min_length=1)


class OrganizedInformation(BaseModel):
    """Describe the reading product and any independently grounded follow-up."""

    worth_archiving: bool
    worth_proposing: bool
    understanding: str
    key_points: list[str]
    archive_requirements: str = Field(description="Grounded reason to retain this material and the evidence available for Curator.")
    follow_up: FollowUp | None
    limitations: list[str]

    possible_outputs: SkipJsonSchema[list[str] | None] = Field(default=None, exclude_if=lambda v: v is None)

    @model_validator(mode="before")
    @classmethod
    def read_decisions(cls, values):
        if not isinstance(values, dict):
            return values
        if "possible_outputs" in values and "follow_up" not in values:
            # Earlier checkpoints stored suggestions and independent routing flags.
            # Keep their original route without turning suggestions into user requests.
            return {"worth_archiving": False, "worth_proposing": True,
                    "archive_requirements": "", "follow_up": None, **values}
        return values

    @model_validator(mode="after")
    def check_decisions(self):
        if self.possible_outputs is None:
            if self.worth_archiving != bool(self.archive_requirements.strip()):
                raise ValueError("Supply archive requirements exactly when a reading product is warranted")
            if self.worth_proposing != (self.follow_up is not None):
                raise ValueError("A proposal requires outstanding work and its basis")
        return self
