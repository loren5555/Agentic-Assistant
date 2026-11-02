"""Raw captures and organized briefs independent of their storage provider."""

from typing import Literal
import hashlib
import json

from pydantic import BaseModel, Field

CaptureKind = Literal["notero", "simpread"]


class RawCapture(BaseModel):
    """Preserve the material actually available for reading.

    Attributes:
        kind: Raw input collection, not an organized output database.
        page_id: Original Notion page identity.
        url: Original capture link.
        title: Source title.
        text: Captured content, notes, and metadata; not necessarily full text.
        metadata: Source metadata without timestamps or agent bookkeeping.
        revision: Current storage edit timestamp for diagnostics.
        full_text_verified: Whether acquisition independently verified original text.
    """

    kind: CaptureKind
    page_id: str
    url: str
    title: str
    text: str
    metadata: dict = Field(default_factory=dict)
    revision: str = ""
    full_text_verified: bool = False

    @property
    def fingerprint(self) -> str:
        """Hash meaningful content instead of synchronization timestamps.

        Returns:
            Digest identifying the captured material being processed.
        """
        material = {
            "title": self.title, "text": self.text, "metadata": self.metadata,
            "full_text_verified": self.full_text_verified,
        }
        serialized = json.dumps(material, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        return digest

    @property
    def identity(self) -> str:
        """Prefer bibliographic identity over a storage-specific page identifier.

        Returns:
            Zotero URI, normalized DOI, or original capture page identity.
        """
        for name, value in self.metadata.items():
            if (
                "zotero" in name.lower() and "uri" in name.lower()
                and isinstance(value, str) and value
            ):
                return value
        for name, value in self.metadata.items():
            if name.lower() == "doi" and isinstance(value, str) and value:
                return "doi:" + value.lower().removeprefix("https://doi.org/")
        identity = f"{self.kind}:{self.page_id}"
        return identity


class CaptureBatch(BaseModel):
    """Return a bounded input page and the next source cursor.

    Attributes:
        captures: Source materials read during this query.
        next_cursor: Continuation token, or None at the end of the collection.
    """

    captures: list[RawCapture]
    next_cursor: str | None = None


class PaperReadingMetadata(BaseModel):
    """Describe reading fields supported by the supplied paper material.

    Attributes:
        abstract: Original abstract, only when actually supplied.
        summary: Concise reading summary at the available evidence level.
        publication_date: Source publication date, preserving partial dates.
        publication: Journal, conference, or repository explicitly named by the source.
        keywords: Research topics and methods useful for browsing.
        tags: Broad research areas for organizing the reading library.
        code_url: Explicitly supplied official code link, or empty when unknown.
    """

    abstract: str = ""
    summary: str = ""
    publication_date: str = ""
    publication: str = ""
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    code_url: str = ""


class CaptureBrief(BaseModel):
    """Describe a grounded organized output or the need for human-approved work.

    Attributes:
        destination: Paper, reusable knowledge, or a proposal requiring review.
        title: Organized output title.
        content: Brief with claims, evidence, limitations, and source links.
        evidence_level: Material actually read, not the apparent file type.
        reason: Classification explanation or proposed investigation rationale.
        reading: Structured paper reading fields, separate from citation management.
    """

    destination: Literal["papers", "knowledge", "proposal"]
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    evidence_level: Literal["full_text", "abstract", "notes", "metadata"]
    reason: str = Field(min_length=1)
    reading: PaperReadingMetadata = Field(default_factory=PaperReadingMetadata)


class CaptureReceipt(BaseModel):
    """A verified organized destination write.

    Attributes:
        page_id: Published output identifier.
        url: Human-readable destination link.
        key: Stable source identity used for retry-safe publication.
        fingerprint: Source content version represented by this output.
    """

    page_id: str
    url: str
    key: str
    fingerprint: str
