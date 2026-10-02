"""Adapt an inbox record into input for the general assistance workflow."""

from assistant.protocol.inbox import InboxSourceProtocol
from assistant.schemas.input import SourceReference, WorkInput


def read_inbox(source: InboxSourceProtocol, source_id: str) -> WorkInput:
    record = source.fetch(source_id)

    # Keep the source identity and revision for attribution after routing.
    reference = SourceReference(
        namespace=record.source,
        id=record.source_id,
        revision=record.revision,
    )
    input = WorkInput(
        text=record.text,
        sources=[reference],
        simulated=record.simulated,
    )

    return input
