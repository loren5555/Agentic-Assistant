"""Format saved workflow outputs consistently for clients and the report UI."""

import base64
import binascii
import pickletools

from pydantic import BaseModel
from assistant.components.recommendations.recommender.models import (
    CATEGORIES,
    RecommendationRun,
)


def error_message(error, fallback: str) -> str:
    """Show the message from a saved exception, omitting serialized state and headers."""
    if not isinstance(error, str) or not error.startswith("gAS"):
        return str(error or fallback)

    # DBOS can return the original pickle when an SDK exception cannot be
    # reconstructed from its message alone. Inspect the constructor argument
    # without loading any classes or reading the HTTP response state.
    try:
        raw = base64.b64decode(error, validate=True)
        ops = ((op.name, arg) for op, arg, _ in pickletools.genops(raw)
               if op.name not in {"PROTO", "FRAME", "MEMOIZE"})
        string_ops = {"SHORT_BINUNICODE", "BINUNICODE", "BINUNICODE8"}
        module, cls, constructor, message, args = (next(ops) for _ in range(5))
        if (module[0] in string_ops and cls[0] in string_ops
                and constructor[0] == "STACK_GLOBAL" and message[0] in string_ops
                and args[0] == "TUPLE1"):
            return f"{cls[1]}: {message[1][:2000]}"
    except (ValueError, binascii.Error, EOFError, StopIteration, RuntimeError):
        pass
    return f"{fallback}. See the service log for the original error."


def result_document(output):
    """Prepare business outputs for HTTP and CLI without exposing provider credentials.

    Args:
        output: Workflow report or collection of verified destination links.
    """
    document = (
        output.model_dump(mode="json") if isinstance(output, BaseModel) else output
    )
    if isinstance(output, RecommendationRun):
        # Detailed provider events remain in the durable/local report, while the
        # command output stays focused on recommendations and source limitations.
        document = output.model_dump(
            mode="json",
            exclude={
                "failed_processes": True,
                "discovery": {"process"},
                "evidence": {"__all__": {"process"}},
                "selected": {"__all__": {"evidence": {"process"}}},
            },
        )
        counts = {category: 0 for category in CATEGORIES}
        real = [entry for entry in output.selected if not entry.candidate.demo]
        for _, entry in zip(output.published, real):
            counts[entry.assessment.category] += 1
        document.update(
            publication_count=len(output.published),
            publication_counts=counts,
            short_term_interest_changes=[],
        )
    return document
