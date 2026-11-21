"""Turn one rec5 topic recommendation into attributed Discovery Pool candidates."""

from assistant.components.recommendations.discovery.models import PaperCandidate, SourceQuality
from logger import get_logger, trace_call
from plugins._shared import aminer

logger = get_logger("plugins.recommendations.sources.aminer")


@trace_call("component", "aminer.recommend")
async def recommend(direction, limit: int, *, api_key: str) -> list[PaperCandidate]:
    size = min(10, limit)
    logger.info("AMiner rec5 started: topic=%r candidates_requested=%d.", direction.query, size)
    groups = await aminer.post(
        "v3/paper/rec5", {"topics": [direction.query], "size": size}, api_key=api_key, timeout=60,
        headers={"X-Platform": "unknown", "X-Skill-Name": "aminer-daily-paper",
                 "X-Skill-Version": "1.1.2"},
    )
    candidates = []
    for group in groups:
        for row in group["papers"]:
            if not row.get("paper_id") or not row.get("title"):
                continue
            page = f"https://www.aminer.cn/pub/{row['paper_id']}"
            links = row.get("links") or {}
            reason = direction.query
            if row.get("year"):
                reason += f" (AMiner publication year: {row['year']})"
            candidates.append(PaperCandidate(
                id=f"aminer:{row['paper_id']}", title=row["title"],
                url=links.get("arxiv") or row.get("paper_url") or page,
                doi=row.get("doi") or "",
                discovery_sources=["aminer"], breadth=direction.breadth,
                discovery_reason=reason, summary=row.get("summary") or "",
                topics=row.get("keywords") or [],
                quality=SourceQuality(authors=row.get("authors") or [], sources=[page]),
            ))
    logger.info("AMiner rec5 completed: topic=%r candidates=%d.", direction.query, len(candidates[:size]))
    return candidates[:size]
