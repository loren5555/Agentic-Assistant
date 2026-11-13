"""Checkpoint acquisition inputs, source work and reusable search directions.

Interests, rolling publication coverage and available Pool stock enter a bounded
Collector request. Weekly directions are retained locally for six cheap daily scans.
Source failures stay visible; the editorial workflow may still use existing stock.
"""

import json
from collections import Counter

from dbos import DBOS
from assistant.components.recommendations.collector.models import (
    CollectionRequest,
    CollectionResult,
    SearchDirection,
)
from assistant.components.recommendations.collector.policy import (
    coverage_table,
    age_bucket,
)
from logger import trace_call


@DBOS.step(name="ResearchWorkflows.collection_brief")
@trace_call("step", "prepare_collection")
def collection_brief(self, day, mode, interests):
    """Read stock and coverage before any source query decides what to acquire."""
    self.logger.info(
        "Preparing collection: mode=%s interests=%d.", mode, len(interests)
    )
    policy = self.settings.collector
    entries = self.services.discovery_pool.read_candidates()
    counts = self.index.coverage_counts(day, self.settings.coverage_days)
    cells = coverage_table(
        self.settings.exploration,
        self.settings.ages,
        counts,
        self.settings.selected_count,
    )
    stock = Counter(
        (entry.candidate.breadth, age_bucket(entry.candidate.published_date, day))
        for entry in entries
    )
    for cell in cells:
        cell.available = stock[(cell.breadth, cell.age)]
    plan_path = self.directory / "collector-directions.json"
    directions = (
        [
            SearchDirection.model_validate(item)
            for item in json.loads(plan_path.read_text())["directions"]
        ]
        if plan_path.exists()
        else []
    )
    self.logger.info(
        "Collection brief ready: pool=%d coverage_cells=%d saved_directions=%d.",
        len(entries),
        len(cells),
        len(directions),
    )
    return CollectionRequest(
        day=day,
        mode=mode,
        interests=interests,
        coverage=cells,
        pool=[entry.candidate for entry in entries[: policy.context_pool_size]],
        directions=directions,
        max_queries=policy.max_queries,
        max_candidates=policy.max_candidates,
    )


@DBOS.step(name="ResearchWorkflows.collect")
@trace_call("step", "collect_research")
async def collect(self, request: CollectionRequest) -> CollectionResult:
    """Checkpoint the whole acquisition, including Codex telemetry and source limits."""
    self.logger.info("Research collection started: mode=%s.", request.mode)
    result = await self.services.collector(request.mode).collect(request)
    self.logger.info(
        "Research collection completed: mode=%s candidates=%d failures=%d.",
        request.mode,
        len(result.discovery.candidates),
        len(result.failures),
    )
    return result


@DBOS.step(name="ResearchWorkflows.prepare_pool_display")
@trace_call("step", "prepare_pool_display")
async def prepare_pool_display(self, result: CollectionResult) -> CollectionResult:
    """Translate API metadata for Pool without replacing paper titles or evidence."""
    pending = [
        candidate
        for candidate in result.discovery.candidates
        if not candidate.display_title
    ]
    if not pending:
        return result
    self.logger.info("Preparing Chinese Pool summaries: candidates=%d.", len(pending))
    translations = await self.services.recommender.translate_pool(pending)
    mapped = {item.id: item for item in translations.items}
    if set(mapped) != {candidate.id for candidate in pending}:
        raise ValueError("Pool translation did not preserve all candidate identities")
    for candidate in pending:
        display = mapped[candidate.id]
        candidate.display_title = display.display_title
        candidate.summary = display.summary
        candidate.topics = display.topics
        candidate.discovery_reason = display.discovery_reason
    self.logger.info("Chinese Pool summaries prepared: candidates=%d.", len(pending))
    return result


@DBOS.step(name="ResearchWorkflows.save_directions")
@trace_call("step", "save_collection_directions")
def save_directions(self, result: CollectionResult, day: str) -> None:
    """Save weekly reusable queries atomically; daily refresh does not replace them."""
    if result.mode != "deep" or not result.directions:
        return
    self.directory.mkdir(parents=True, exist_ok=True)
    path = self.directory / "collector-directions.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {"day": day, "directions": [d.model_dump() for d in result.directions]},
            ensure_ascii=False,
            indent=2,
        )
    )
    temporary.replace(path)
    self.logger.info(
        "Weekly search directions saved: directions=%d.", len(result.directions)
    )
