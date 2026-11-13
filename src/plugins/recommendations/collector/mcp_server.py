"""Expose bounded public OpenReview tools only to one weekly Codex invocation.

Input origin: the Collector host passes nonsecret source settings and call budgets
through environment variables. OpenReview credentials remain in host variables.
Output destination: structured public source material returned over MCP stdio.
No Notion, database mutation, shell or arbitrary URL fetch tools are exposed.
"""

import asyncio
import json
import os

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from assistant.components.recommendations.collector.models import SearchDirection
from plugins.recommendations.sources.openreview import OpenReviewSource


def build_server():
    """Register source tools with a shared per-run API-call budget."""
    server = MCPServer("research_sources", log_level="WARNING")
    options = json.loads(os.environ.get("ASSISTANT_COLLECTOR_SOURCE_CONFIG", "{}"))
    source = OpenReviewSource(options)
    remaining = int(os.environ.get("ASSISTANT_COLLECTOR_MAX_QUERIES", "6"))
    day = os.environ["ASSISTANT_COLLECTOR_DAY"]
    lock = asyncio.Lock()

    async def reserve():
        """Charge every source invocation before a request can consume resources."""
        nonlocal remaining
        async with lock:
            if remaining <= 0:
                raise ValueError(
                    "Source tool budget exhausted; finish using existing evidence"
                )
            remaining -= 1

    @server.tool(
        annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False)
    )
    async def search_openreview(query: str, breadth: str, age: str) -> dict:
        """Find public OpenReview papers. breadth: Core/Broader/Neighboring/Cross-disciplinary.

        age: week/month/quarter/half_year/year/three_years/older. Use concrete English
        queries from the coverage brief. Results preserve original titles and dates.
        """
        await reserve()
        direction = SearchDirection(query=query, breadth=breadth, age=age)
        candidates, notes = await source.search(direction, day, 20)
        return {
            "candidates": [c.model_dump() for c in candidates],
            "limitations": notes,
        }

    @server.tool(
        annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False)
    )
    async def read_openreview_discussion(forum_id: str) -> dict:
        """Read a paper's original abstract and publicly visible review/author thread.

        Use a forum ID returned by search. Return raw review scales and reply links;
        this material does not establish full paper-text access.
        """
        await reserve()
        return (await source.read(forum_id)).model_dump()

    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")
