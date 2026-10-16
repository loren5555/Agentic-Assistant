"""Apply evidence gates and daily maxima independently from discovery providers."""

from collections.abc import Mapping

from assistant.protocol.recommendation import (
    DiscoveryProtocol, EvidenceReaderProtocol, RecommenderProtocol,
)
from assistant.schemas.recommendation import (
    CATEGORIES, Recommendation, RecommendationRun, ResearchInterest,
)


async def evaluate_recommendations(
    discovery: DiscoveryProtocol, reader: EvidenceReaderProtocol,
    recommender: RecommenderProtocol, interests: list[ResearchInterest],
    maxima: Mapping[str, int] | None = None,
    existing_keys: set[str] | None = None,
) -> RecommendationRun:
    """Assess sources without publishing, preserving rejection and failure reasons.

    Args:
        discovery: Source-search capability.
        reader: Primary-text retrieval capability.
        recommender: Evidence assessment capability.
        interests: Read-only research priorities.
        maxima: Per-category limits; unspecified categories default to one.
        existing_keys: Previously published DOI or provider identities.

    Returns:
        Selected reports and exclusions, with no claimed publications.
    """
    report = RecommendationRun()
    limits = {category: 1 for category in CATEGORIES}
    if maxima is not None:
        limits.update(maxima)
    counts = {category: 0 for category in CATEGORIES}
    seen = set(existing_keys or ())

    for candidate in discovery.discover(interests):
        report.demo = report.demo or candidate.demo
        identity = candidate.doi.strip().lower() or candidate.id
        if identity in seen:
            report.rejected[candidate.id] = "Duplicate source identity"
            continue
        seen.add(identity)

        try:
            evidence = reader.read(candidate)
        except Exception as error:
            # Source retrieval is an independent recovery boundary: keep other sources usable.
            report.source_failures[candidate.id] = f"{type(error).__name__}: {error}"
            report.rejected[candidate.id] = "Primary evidence retrieval failed"
            continue
        if evidence.failure:
            report.source_failures[candidate.id] = evidence.failure
        if not evidence.primary_source or not evidence.text.strip():
            report.rejected[candidate.id] = "Accessible primary evidence required"
            continue

        assessment = await recommender.assess(candidate, evidence, interests)
        category = assessment.category
        if not assessment.qualified or category is None:
            report.rejected[candidate.id] = assessment.reason
            continue
        if category == "Mainline Deep Read" and not evidence.full_text:
            report.rejected[candidate.id] = "Mainline Deep Read requires complete primary text"
            continue
        if counts[category] >= limits[category]:
            report.rejected[candidate.id] = f"Daily maximum reached for {category}"
            continue

        counts[category] += 1
        report.selected.append(Recommendation(candidate=candidate, evidence=evidence,
                                               assessment=assessment))
    return report
