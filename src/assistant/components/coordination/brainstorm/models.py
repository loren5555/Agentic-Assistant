"""Research inputs and exploration reports shared by retrieval, synthesis and triage.

Research notes identify actual source pages and revisions. Candidate items describe
possible independent decisions. Their URLs travel with the claims into human review.
"""

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic.json_schema import SkipJsonSchema

from assistant.runtime.records import ExecutionProcess

BrainstormMode = Literal["material", "idea"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ResearchNote(BaseModel):
    page_id: str
    url: str
    title: str
    collection: Literal["paper", "knowledge", "idea", "spark", "workbench"]
    revision: str
    text: str


class BrainstormContext(BaseModel):
    mode: BrainstormMode
    seed: ResearchNote
    history: list[ResearchNote]


class CandidateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Text
    claim: Text
    evidence: list[Text] = Field(min_length=1)
    next_step: Text

    @field_validator("evidence")
    @classmethod
    def check_sources(cls, values: list[str]) -> list[str]:
        for value in values:
            url = urlsplit(value)
            if url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password:
                raise ValueError("Candidate evidence must contain source URLs")
        return list(dict.fromkeys(values))


class ExplorationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: Text
    findings: list[Text]
    candidates: list[CandidateItem] = Field(max_length=6)
    limitations: list[Text]
    process: SkipJsonSchema[ExecutionProcess | None] = None
