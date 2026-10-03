"""Materials, reviewable proposals, and tasks prepared on a workbench."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from assistant.schemas.process import ExecutionProcess
from assistant.schemas.task import TaskResult
from assistant.schemas.curation import CurationDecision


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

    kind: Literal["inbox", "todo"]
    page_id: str
    url: str
    title: str
    text: str
    revision: str


class Proposal(BaseModel):
    """Explain a proposed task in a report suitable for human review.

    Attributes:
        title: Short proposal title.
        understanding: Interpretation of the supplied material.
        purpose: Intended goal of the proposed work.
        reason: Why this work is useful or necessary.
        action: Concrete operation proposed for approval.
        plan: Steps within the proposed scope.
        expected_result: Deliverable and criteria for judging it.
        source_fingerprint: Content digest assigned by the provider.
        version: Proposal revision assigned by the provider.
        process: Actual drafting telemetry, excluded from model output schemas.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    understanding: str
    purpose: str
    reason: str
    action: str
    plan: list[str]
    expected_result: str
    source_fingerprint: SkipJsonSchema[str] = ""
    version: SkipJsonSchema[int] = 1
    process: SkipJsonSchema[ExecutionProcess | None] = None


class WorkbenchItem(BaseModel):
    """Read a workbench row without coupling callers to Notion properties.

    Attributes:
        page_id: Workbench page identifier.
        url: Human-facing workbench link.
        title: Current proposal title.
        status: Proposal lifecycle state.
        human_review: Human approval decision.
        human_instruction: Human feedback for planning or execution.
        result_review: Human decision about the execution result.
        result_feedback: Human instructions for redoing the result.
        source_url: Link to original input.
        source_kind: Source database role, when managed by this workflow.
        proposal: Current structured proposal, or None for unmanaged records.
        result: Latest saved deliverable, if execution has completed.
        curation: Current extraction decision and verified destination links.
    """

    page_id: str
    url: str
    title: str
    status: str
    human_review: str
    human_instruction: str
    result_review: str
    result_feedback: str
    source_url: str
    source_kind: Literal["inbox", "todo"] | None = None
    proposal: Proposal | None = None
    result: TaskResult | None = None
    curation: CurationDecision | None = None


class ProposedTask(BaseModel):
    """Hand off an approved proposal or requested redo to an executor.

    Attributes:
        workbench_url: Proposal and review record.
        proposal: Approved scope, including its version.
        instruction: Human instructions supplementing this task.
        redo: Whether this task addresses an unqualified result.
    """

    workbench_url: str
    proposal: Proposal
    instruction: str
    redo: bool = False


class ProposalCycle(BaseModel):
    """Summarize one intake and review pass.

    Attributes:
        submitted: Newly submitted proposal links.
        revised: Resubmitted proposal links.
        deprecated: Rejected proposal links.
        waiting: Proposals waiting for review or clarification.
    """

    submitted: list[str] = Field(default_factory=list)
    revised: list[str] = Field(default_factory=list)
    deprecated: list[str] = Field(default_factory=list)
    waiting: list[str] = Field(default_factory=list)
