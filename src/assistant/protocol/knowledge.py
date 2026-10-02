"""The provider interface for publishing and verifying knowledge drafts."""

from typing import Protocol

from assistant.schemas.knowledge import DraftReceipt, KnowledgeNote


class KnowledgePublisherProtocol(Protocol):
    def publish_draft(self, note: KnowledgeNote) -> DraftReceipt: ...

    def read_draft(self, draft_id: str) -> DraftReceipt: ...
