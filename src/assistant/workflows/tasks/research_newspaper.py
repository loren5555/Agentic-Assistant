"""Run acquisition before the shared daily newspaper edition.

Two DBOS schedules submit deep/light dispatches. Deep acquisition is reused within
an ISO week; light acquisition is reused within a day. Edition identity is shared
across both modes so collecting twice cannot publish a second daily newspaper.
"""

from datetime import date
import hashlib

from dbos import DBOS
from assistant.runtime.recovery import invoke
from logger import trace_call


@DBOS.workflow(name="ResearchWorkflows.collect_research")
@trace_call("workflow", "collect_research")
async def collect_research(self, day: str, mode: str):
    """Collect a reusable research batch with independently retained checkpoints."""
    interests = self.read_preferences()
    request = self.collection_brief(day, mode, interests)
    result = await self.collect(request)
    result = await self.prepare_pool_display(result)
    self.save_directions(result, day)
    return result


@DBOS.workflow(name="ResearchWorkflows.store_collection")
@trace_call("workflow", "store_collection")
async def store_collection(self, discovery, day: str):
    """Merge one acquired batch even when today's edition is already published."""
    self.refresh_pool(discovery.candidates, day)


@DBOS.workflow(name="ResearchWorkflows.daily_newspaper")
@trace_call("workflow", "daily_newspaper")
async def daily_newspaper(self, day: str, mode: str = "auto"):
    """Await the selected collector, then publish one quality-gated daily edition."""
    if self.demo:
        return await self.recommend_papers(day)
    if mode == "auto":
        mode = (
            "deep"
            if date.fromisoformat(day).weekday() == self.settings.collector.deep_weekday
            else "light"
        )
    if mode not in {"deep", "light"}:
        raise ValueError(f"Unknown collection mode: {mode}")
    stamp = date.fromisoformat(day)
    year, week, _ = stamp.isocalendar()
    period = f"{year}-W{week:02d}" if mode == "deep" else day
    self.logger.info("Daily newspaper started: day=%s collection_mode=%s.", day, mode)
    try:
        collection = await invoke(
            f"collection:v1:{mode}:{period}", self.collect_research, day, mode
        )
        discovery = collection.discovery
    except Exception as error:
        from assistant.components.recommendations.discovery.models import (
            DiscoveryResult,
        )

        self.logger.exception("Collection failed; trying the existing Pool.")
        discovery = DiscoveryResult(
            candidates=[],
            notes=["Collector failed; existing Pool remains eligible"],
            source_failures={"collector": f"{type(error).__name__}: {error}"},
        )
        discovery.process = getattr(error, "process", None)
    if discovery.candidates:
        await invoke(f"pool:collection-v1:{mode}:{period}", self.store_collection, discovery, day)
    policy = self.settings.model_dump_json()
    policy_key = hashlib.sha256(policy.encode()).hexdigest()[:12]
    result = await invoke(
        f"edition:collector-v1:{day}:{policy_key}",
        self.recommend_papers,
        day,
        discovery,
    )
    self.logger.info(
        "Daily newspaper completed: mode=%s published=%d.", mode, len(result.published)
    )
    return result
