"""Refresh research using saved weekly directions and public source tools.

No model is invoked here. Coverage deficits and existing stock order reusable
queries; OpenReview returns attributed candidates and explicit retrieval limits.
"""

from collections import Counter

from assistant.components.recommendations.collector.models import (
    CollectionRequest,
    CollectionResult,
    SearchDirection,
)
from assistant.components.recommendations.collector.policy import age_bucket
from assistant.components.recommendations.discovery.identity import candidate_identity
from assistant.components.recommendations.discovery.models import DiscoveryResult
from plugins.recommendations.sources.openreview import OpenReviewSource
from logger import get_logger, trace_call


def search_directions(request: CollectionRequest) -> list[SearchDirection]:
    """Prioritize reusable directions by coverage deficit and available stock."""
    positive = [
        interest
        for interest in request.interests
        if not interest.id.startswith("avoid:")
    ]
    if not positive:
        return []
    stock = Counter(
        (c.breadth, age_bucket(c.published_date, request.day)) for c in request.pool
    )
    cells = sorted(
        request.coverage,
        key=lambda cell: cell.deficit
        - max(cell.available, stock[(cell.breadth, cell.age)]),
        reverse=True,
    )
    planned = []
    for position, cell in enumerate(cells):
        if cell.target <= 0:
            continue
        saved = [
            d
            for d in request.directions
            if d.breadth == cell.breadth and d.age == cell.age
        ]
        if saved:
            planned.append(saved[position % len(saved)])
        elif any(d.breadth == cell.breadth for d in request.directions):
            related = next(d for d in request.directions if d.breadth == cell.breadth)
            planned.append(related.model_copy(update={"age": cell.age}))
        else:
            topic = sorted(positive, key=lambda i: i.priority, reverse=True)[
                position % len(positive)
            ].title
            suffix = {
                "Core": "",
                "Broader": " deep learning",
                "Neighboring": " control game theory",
                "Cross-disciplinary": " mathematical foundations",
            }[cell.breadth]
            planned.append(
                SearchDirection(
                    query=topic + suffix,
                    breadth=cell.breadth,
                    age=cell.age,
                    reason="Coverage-driven query; weekly exploration can refine this direction",
                )
            )
    # Keep one opportunity per cell before repeating saved queries from that cell.
    unique = {(d.query, d.breadth, d.age): d for d in planned}
    return list(unique.values())[: request.max_queries]


def merge_candidates(candidates):
    """Merge exact bibliographic identities and retain all retrieval provenance."""
    result = {}
    aliases = {}
    for candidate in candidates:
        key = candidate_identity(candidate)
        alias = candidate_identity(candidate.model_copy(update={"doi": ""}))
        known = key if key in result else aliases.get(alias)
        if known:
            previous = result[known]
            previous.discovery_sources = list(
                dict.fromkeys(previous.discovery_sources + candidate.discovery_sources)
            )
            previous.openreview_forum = (
                previous.openreview_forum or candidate.openreview_forum
            )
            continue
        result[key] = candidate
        aliases[alias] = key
    return list(result.values())


class Collector:
    """Execute bounded, coverage-aware source refreshes without Codex or local LLMs."""

    def __init__(self, options, source_options) -> None:
        """Bind public API tools independently of model settings."""
        self.source = OpenReviewSource(source_options)
        self.logger = get_logger("plugins.recommendations.collector.local")

    @trace_call("component", "collector.collect")
    async def collect(self, request: CollectionRequest) -> CollectionResult:
        """Acquire candidates for prioritized cells and report partial source failure."""
        directions = search_directions(request)
        self.logger.info(
            "kind=script provider=local Collection started: queries=%d mode=%s.",
            len(directions),
            request.mode,
        )
        candidates, notes, failures = [], [], {}
        for position, direction in enumerate(directions, 1):
            if len(candidates) >= request.max_candidates:
                break
            try:
                found, limits = await self.source.search(
                    direction, request.day, request.max_candidates - len(candidates)
                )
                candidates.extend(found)
                notes.extend(limits)
            except Exception as error:
                failures[f"openreview:{position}"] = f"{type(error).__name__}: {error}"
                self.logger.warning(
                    "OpenReview collection query failed: query=%r error=%s.",
                    direction.query,
                    error,
                )
        candidates = merge_candidates(candidates)
        self.logger.info(
            "kind=script provider=local Collection completed: candidates=%d source_failures=%d.",
            len(candidates),
            len(failures),
        )
        return CollectionResult(
            mode=request.mode,
            directions=directions,
            failures=failures,
            discovery=DiscoveryResult(
                candidates=candidates, notes=notes, source_failures=failures
            ),
        )
