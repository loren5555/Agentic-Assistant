"""Format saved workflow outputs consistently for clients and the future report UI."""

from pydantic import BaseModel
from assistant.components.recommendations.recommender.models import (
    CATEGORIES,
    RecommendationRun,
)


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
