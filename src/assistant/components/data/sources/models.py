"""Material submitted for interpretation and proposal drafting."""

from typing import Literal
import hashlib
import json
from pydantic import BaseModel, Field
from assistant.components.execution.planner.models import ExecutionPlan


SourceKind = Literal["inbox", "todo", "notero", "simpread", "paper", "interest", "feed", "pool", "brainstorm"]


class SourceHistory(BaseModel):
    """Retain one feedback round on its original source.

    Attributes:
        key: Stable identity preventing duplicate feedback application.
        workbench_url: Previous proposal and result for human inspection.
        feedback: Human-requested change.
        result: Previous deliverable, when available.
        proposal: Previous proposal, including clarification questions and rationale.
        accepted_plan: Human-qualified plan available to the next proposal.
    """

    key: str
    workbench_url: str
    feedback: str
    result: str = ""
    proposal: str = ""
    accepted_plan: ExecutionPlan | None = None


class SourceArchive(BaseModel):
    """Verified reading product supplied alongside the original material."""

    url: str
    destination: Literal["papers", "knowledge"]
    summary: str
    evidence_level: str


class SourceMaterial(BaseModel):
    """Describe material submitted by a human.

    Attributes:
        kind: Input database containing this material.
        page_id: Source page identifier.
        url: Source link retained after intake closes.
        title: Original input title.
        text: Meaningful source properties and page content.
        revision: Source edit timestamp at intake.
        version: Semantic input version, advanced by reconciliation.
        supplement: Human feedback accumulated without modifying original text.
        history: Prior work and feedback rounds.
        metadata: Source-specific reading and provenance fields.
        full_text_verified: Whether the actual original text was retrieved.
        organization: Derived interpretation, never part of source identity.
    """

    kind: SourceKind
    page_id: str
    url: str
    title: str
    text: str
    revision: str
    version: int = 1
    supplement: str = ""
    history: list[SourceHistory] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    full_text_verified: bool = False
    organization: str = ""
    archive: SourceArchive | None = None
    additional_archives: list[SourceArchive] = Field(default_factory=list, exclude_if=lambda v: not v)

    @property
    def intake_snapshot(self) -> str:
        """Identify a proposal input by its origin, semantic version and edit time."""
        # Pool refreshes and preference edits also advance Notion edit time.
        revision = self.fingerprint if self.kind == "pool" else self.revision
        identity = [self.kind, self.page_id, self.version, revision]
        return "snapshot:" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()

    @property
    def fingerprint(self) -> str:
        """Identify effective input independently of storage bookkeeping.

        Returns:
            Digest covering source content, feedback and semantic version.
        """
        content = self.model_dump(exclude={"revision", "organization", "archive", "additional_archives"})
        return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    @property
    def context_content(self) -> str:
        """Provide complete effective material to stateless reasoning components.

        Returns:
            Original text, current feedback and relevant previous work.
        """
        return json.dumps(self.model_dump(exclude={"revision"}), ensure_ascii=False)
