"""Search configured workspace collections and read current pages for model decisions."""

from collections.abc import Mapping
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID
import re

from httpx import HTTPError
from notion_client import Client
from notion_client.errors import NotionClientErrorBase
from pydantic_ai.toolsets import FunctionToolset

from logger import get_logger, trace_call
from plugins._shared.notion.catalog import metadata, terms
from plugins._shared.notion.config import ArtifactStoreSettings, SourceCollectionSettings
from plugins._shared.notion.markdown import page_markdown
from plugins._shared.notion.sparks import resolve_sparks

Collection = Literal["workbench", "idea", "knowledge", "paper", "research_interest", "spark"]
READ_ERRORS = (HTTPError, NotionClientErrorBase, ValueError)
logger = get_logger("plugins.data.workspace.notion")


def describe(collection, page):
    title, fields = metadata(page)
    summary = next((fields[k] for k in ("Summary", "Reading Summary", "摘要", "Purpose", "Description", "Motivation")
                    if fields.get(k)), "")
    return {"ref": page["id"], "url": page["url"], "collection": collection, "title": title,
            "status": fields.get("Status", fields.get("State", "")),
            "approval": fields.get("Human Review", ""), "acceptance": fields.get("Result Review", ""),
            "summary": summary[:400], "updated": page["last_edited_time"]}


def page_id(ref: str) -> str:
    path = urlsplit(ref.strip()).path.rstrip("/")
    match = re.search(r"([0-9a-fA-F]{32}|[0-9a-fA-F-]{36})$", path)
    if not match:
        raise ValueError("Use a workspace page ID or page URL.")
    return str(UUID(match[1]))


class Workspace:
    """Supply current Notion records as evidence for proposal and retention decisions."""

    def __init__(self, options: Mapping[str, object]):
        self.options = dict(options)
        sources = SourceCollectionSettings.model_validate(options)
        artifacts = ArtifactStoreSettings.model_validate(options)
        self.token = sources.token
        self.collections = {k: v for k, v in {
            "workbench": options.get("workbench_data_source_id"), "knowledge": sources.knowledge_data_source_id,
            "paper": sources.papers_data_source_id, "idea": artifacts.ideas_data_source_id,
            "research_interest": artifacts.research_interests_data_source_id,
            "spark": options.get("sparks_data_source_id"),
        }.items() if v}

    def toolset(self):
        return FunctionToolset(tools=[self.search_workspace, self.read_workspace_item])

    @trace_call("tool", "search_workspace")
    def search_workspace(self, query: str = "", collection: Collection | None = None, offset: int = 0) -> dict:
        """Find related work by title or summary. An empty query lists the metadata catalog.
        Narrow by collection or pass next_offset for more matches. Check errors for incomplete coverage.
        """
        if offset < 0:
            return {"error": "Use a nonnegative offset."}
        found, errors = [], {}
        keywords = set(terms(query))
        phrase = query.strip().casefold()
        logger.info("Searching workspace catalog: collection=%s.", collection or "all")
        with Client(auth=self.token) as client:
            collections = dict(self.collections)
            if collection in (None, "spark") and "spark" not in collections and self.options.get("assistant_page_id"):
                try:
                    collections["spark"] = resolve_sparks(client, self.options)
                except READ_ERRORS as exc:
                    errors["spark"] = type(exc).__name__
            if collection and collection not in collections:
                errors.setdefault(collection, "Collection unavailable")
            for kind, source in collections.items():
                if collection and kind != collection:
                    continue
                args = {"data_source_id": source, "page_size": 100, "result_type": "page"}
                try:
                    while True:
                        batch = client.data_sources.query(**args)
                        for page in batch["results"]:
                            entry = describe(kind, page)
                            title = entry["title"].casefold()
                            text = title + " " + entry["summary"].casefold()
                            score = (4 * len(keywords.intersection(terms(title))) +
                                     len(keywords.intersection(terms(text))) + 8 * bool(phrase and phrase in text))
                            if score or not phrase:
                                found.append((score, entry))
                        if not batch["has_more"]:
                            break
                        args["start_cursor"] = batch["next_cursor"]
                except READ_ERRORS as exc:
                    errors[kind] = type(exc).__name__
        found.sort(key=lambda pair: (pair[0], pair[1]["updated"], pair[1]["ref"]), reverse=True)
        end = offset + 15
        if errors:
            logger.warning("Workspace search incomplete: matches=%d unavailable=%s.", len(found), errors)
        else:
            logger.info("Workspace search completed: matches=%d.", len(found))
        return {"items": [entry for _, entry in found[offset:end]], "matches": len(found),
                "next_offset": end if end < len(found) else None, "errors": errors}

    def read_for_writing(self, ref: str, collection: str) -> dict:
        """Load the full authorized page in one request sequence for a known writing target."""
        page = self._read_page(ref)
        if page["collection"] != collection:
            raise ValueError(f"Writing target belongs to {page['collection']}, expected {collection}")
        return page

    @trace_call("tool", "read_workspace_item")
    def read_workspace_item(self, ref: str, offset: int = 0) -> dict:
        """Read current metadata and Markdown for a workspace page by ID or URL.
        For long pages continue with next_offset. An error means the page could not be read.
        """
        if offset < 0:
            return {"error": "Use a nonnegative offset."}
        logger.info("Reading workspace page.", extra={"details": {"ref": ref}})
        try:
            entry = self._read_page(ref)
            body = entry["content"]
        except READ_ERRORS as exc:
            logger.warning("Workspace page unavailable: %s.", type(exc).__name__)
            return {"error": "Workspace page unavailable or incomplete", "reason": type(exc).__name__}
        end = offset + 8000
        logger.info("Workspace page read: title=%r.", entry["title"])
        return {**entry, "content": body[offset:end], "next_offset": end if end < len(body) else None}

    def _read_page(self, ref: str) -> dict:
        with Client(auth=self.token) as client:
            page = client.pages.retrieve(page_id=page_id(ref))
            parent = page.get("parent", {}).get("data_source_id", "").replace("-", "")
            kind = next((k for k, v in self.collections.items() if v.replace("-", "") == parent), None)
            if not kind and parent and self.options.get("assistant_page_id"):
                if parent == resolve_sparks(client, self.options).replace("-", ""):
                    kind = "spark"
            if not kind or page.get("archived") or page.get("in_trash"):
                raise ValueError("Page outside active workspace collections")
            body = page_markdown(client, page["id"])
            entry = describe(kind, page)
        return {**entry, "content": body}
