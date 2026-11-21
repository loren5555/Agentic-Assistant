"""Represent the Proposer's single editorial decision over an exploration report.

Candidate numbers refer to the ordered report (starting at one). A proposal may group
related findings. Omitted candidates remain available in the saved report.
"""

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator
from pydantic.json_schema import SkipJsonSchema

from assistant.components.coordination.proposer.models import Proposal
from assistant.runtime.records import ExecutionProcess


class CandidateProposal(BaseModel):
    """The report items covered by one concrete review decision."""

    model_config = ConfigDict(extra="forbid")

    candidate_numbers: list[PositiveInt] = Field(min_length=1)
    proposal: Proposal


class ReportAssessment(BaseModel):
    """Record the selection rationale, reviewable proposals and call telemetry."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)
    proposals: list[CandidateProposal]
    process: SkipJsonSchema[ExecutionProcess | None] = None

    @model_validator(mode="after")
    def independent_decisions(self):
        numbers = [n for decision in self.proposals for n in decision.candidate_numbers]
        if len(set(numbers)) != len(numbers):
            raise ValueError("Each report candidate may support one review decision")
        return self
