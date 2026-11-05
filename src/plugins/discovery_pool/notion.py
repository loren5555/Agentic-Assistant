"""Maintain the Assistant-owned discovery cache in Notion.

Input origin:
    Public Discovery produces lightweight, attributed source descriptions.
Output destination:
    Discovery Pool displays recent finds and supplies Recommender candidates.
Responsibility:
    Merge by canonical identity, preserve human feedback, record selection and
    archive oldest unliked cache rows beyond capacity. Feed retains selected reports.
"""

from collections.abc import Mapping
from datetime import date
import hashlib

from notion_client import Client

from assistant.components.discovery_pool.models import DiscoveryEntry
from assistant.components.recommendations.identity import candidate_identity
from assistant.components.recommendations.models import PaperCandidate
from logger import get_logger, trace_call
from plugins._shared.notion.config import ResearchFeedSettings


def text(value: str) -> list[dict]:
    """Split an owned text property into Notion-sized fragments."""
    return [{"text": {"content": value[i:i + 2000]}} for i in range(0, len(value), 2000)]


def plain(prop: dict) -> str:
    """Read rich text or title data from the Notion response."""
    return "".join(p.get("plain_text", p.get("text", {}).get("content", ""))
                   for p in prop.get(prop.get("type", "rich_text"), []))


def quality_notes(candidate: PaperCandidate) -> str:
    """Summarize verified context and unknowns for a Chinese quick skim."""
    quality = candidate.quality
    status = {"Published": "已发表", "Accepted": "已接收", "Preprint": "预印本", "Unknown": "发表状态待核实"}[quality.status]
    parts = [status]
    if quality.rank:
        parts.append(quality.rank)
    if quality.authors:
        parts.append("作者：" + "、".join(quality.authors[:5]))
    if quality.author_context:
        parts.append(quality.author_context)
    if quality.novelty:
        parts.append("新意：" + quality.novelty)
    parts.extend(quality.limitations)
    if not quality.sources:
        parts.append("发表渠道、分区与作者背景尚未核验")
    return "；".join(parts)


def presentation(candidate: PaperCandidate) -> dict:
    """Build owned Chinese display fields without changing source identity."""
    return {
        "Name": {"title": text(candidate.display_title or candidate.title)},
        "Summary": {"rich_text": text(candidate.summary or candidate.discovery_reason)},
        "Venue": {"rich_text": text(candidate.quality.venue)},
        "Quality Notes": {"rich_text": text(quality_notes(candidate))},
        "Topics": {"multi_select": [{"name": topic.replace(",", " ")[:100]} for topic in candidate.topics[:10] if topic.strip()]},
        "Candidate Data": {"rich_text": text(candidate.model_dump_json())},
    }


class DiscoveryPool:
    """Own bounded cache persistence without changing source research databases."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind pool identity and connection; no network work occurs here."""
        self.settings = ResearchFeedSettings.model_validate(options)
        self.source_id = self.settings.discovery_pool_data_source_id
        self.logger = get_logger("plugins.discovery_pool.notion")

    def _resolve(self, client: Client) -> str:
        """Locate a setup-created pool without requiring a generated config rewrite."""
        if self.source_id:
            return self.source_id
        if not self.settings.assistant_page_id:
            raise ValueError("Set notion.discovery_pool_data_source_id or notion.assistant_page_id and run setup")
        arguments = {"block_id": self.settings.assistant_page_id, "page_size": 100}
        while True:
            response = client.blocks.children.list(**arguments)
            for block in response["results"]:
                if block["type"] == "child_database" and block["child_database"]["title"] == "Discovery Pool":
                    database = client.databases.retrieve(database_id=block["id"])
                    self.source_id = database["data_sources"][0]["id"]
                    return self.source_id
            if not response["has_more"]:
                break
            arguments["start_cursor"] = response["next_cursor"]
        raise ValueError("Discovery Pool is missing under Assistant; run setup")

    @trace_call("component", "discovery_pool.initialize_schema")
    def initialize_schema(self) -> None:
        """Create a missing Assistant-owned pool, or verify the configured one."""
        self.logger.info("Preparing Discovery Pool.")
        with Client(auth=self.settings.token) as client:
            try:
                source_id = self._resolve(client)
            except ValueError:
                if not self.settings.assistant_page_id:
                    raise
                properties = {"Name": {"title": {}}, "URL": {"url": {}}, "Topics": {"multi_select": {}}}
                for name in ("Stable ID", "Summary", "Candidate Data", "Venue", "Quality Notes"):
                    properties[name] = {"rich_text": {}}
                for name in ("Published", "First Seen", "Last Seen"):
                    properties[name] = {"date": {}}
                for name, options in {
                    "Kind": ["Paper", "Finding", "Method", "Tool", "Dataset", "Other"],
                    "Breadth": ["Core", "Broader", "Neighboring", "Cross-disciplinary"],
                    "State": ["Active", "Selected", "Dormant"],
                    "Feedback": ["Interested", "Not Interested"],
                }.items():
                    properties[name] = {"select": {"options": [{"name": option} for option in options]}}
                database = client.databases.create(
                    parent={"type": "page_id", "page_id": self.settings.assistant_page_id},
                    title=text("Discovery Pool"), initial_data_source={"properties": properties},
                )
                source_id = database["data_sources"][0]["id"]
                self.source_id = source_id
            source = client.data_sources.retrieve(data_source_id=source_id)
            additions = {name: {"rich_text": {}} for name in ("Venue", "Quality Notes") if name not in source["properties"]}
            if additions:
                client.data_sources.update(data_source_id=source_id, properties=additions)
            required = {"Name", "Stable ID", "URL", "Candidate Data", "State", "Feedback", "Topics", "First Seen", "Last Seen", "Published", "Kind", "Breadth", "Summary"}
            if not required <= source["properties"].keys():
                raise ValueError("Discovery Pool lacks required properties")
        self.logger.info("Discovery Pool ready.", extra={"details": {"data_source": source_id}})

    def _query(self, client: Client, condition: dict | None = None) -> list[dict]:
        """Read pool metadata, following pagination without reading page bodies."""
        arguments = {"data_source_id": self._resolve(client), "page_size": 100,
                     "sorts": [{"property": "Last Seen", "direction": "descending"}]}
        if condition:
            arguments["filter"] = condition
        pages = []
        while True:
            response = client.data_sources.query(**arguments)
            pages.extend(response["results"])
            if not response["has_more"]:
                return pages
            arguments["start_cursor"] = response["next_cursor"]

    def _entry(self, page: dict) -> DiscoveryEntry:
        """Reconstruct a cached candidate and its independent human feedback."""
        properties = page["properties"]
        candidate = PaperCandidate.model_validate_json(plain(properties["Candidate Data"]))
        return DiscoveryEntry(candidate=candidate, page_id=page["id"], url=page.get("url", ""),
                              feedback=(properties["Feedback"].get("select") or {}).get("name", ""),
                              selected=(properties["State"].get("select") or {}).get("name") == "Selected")

    @trace_call("component", "discovery_pool.read_feedback")
    def read_feedback(self) -> list[DiscoveryEntry]:
        """Read explicit preferences; unmarked records make no negative signal."""
        self.logger.info("Reading Discovery Pool preferences.")
        with Client(auth=self.settings.token) as client:
            pages = self._query(client, {"property": "Feedback", "select": {"is_not_empty": True}})
            entries = [self._entry(page) for page in pages]
        self.logger.info("Discovery preferences read: marked=%d.", len(entries))
        return entries

    @trace_call("component", "discovery_pool.refresh")
    def refresh(self, candidates: list[PaperCandidate], day: str, limit: int) -> list[DiscoveryEntry]:
        """Merge new finds and retire excess cache rows while preserving likes."""
        self.logger.info("Refreshing Discovery Pool: discovered=%d capacity=%d.", len(candidates), limit)
        with Client(auth=self.settings.token) as client:
            pages = self._query(client)
            known = {plain(page["properties"]["Stable ID"]): page for page in pages}
            aliases = {candidate_identity(self._entry(page).candidate.model_copy(update={"doi": ""})): page for page in pages}
            created = updated = 0
            for candidate in candidates:
                if candidate.demo:
                    continue
                candidate.id = candidate_identity(candidate)
                key = hashlib.sha256(candidate.id.encode()).hexdigest()
                alias = candidate_identity(candidate.model_copy(update={"doi": ""}))
                if key not in known and alias in aliases:
                    known[key] = aliases[alias]
                properties = {
                    **presentation(candidate), "Stable ID": {"rich_text": text(key)},
                    "URL": {"url": candidate.url}, "Kind": {"select": {"name": candidate.kind}},
                    "Breadth": {"select": {"name": candidate.breadth}},
                    "Last Seen": {"date": {"start": day}},
                }
                try:
                    published = date.fromisoformat(candidate.published_date).isoformat()
                except ValueError:
                    published = None
                properties["Published"] = {"date": {"start": published} if published else None}
                if key in known:
                    client.pages.update(page_id=known[key]["id"], properties=properties)
                    updated += 1
                else:
                    properties.update({"First Seen": {"date": {"start": day}}, "State": {"select": {"name": "Active"}}})
                    page = client.pages.create(parent={"type": "data_source_id", "data_source_id": self.source_id}, properties=properties,
                                               markdown=f"原标题：{candidate.title}\n\n原文来源：{candidate.url}\n\n{candidate.summary or candidate.discovery_reason}\n\n## 可能的启发\n\n{candidate.discovery_reason}\n\n## 速览判断\n\n{quality_notes(candidate)}\n\n发现线索，仅作速览；尚未完成精读。")
                    known[key] = page
                    aliases[alias] = page
                    created += 1
            pages = self._query(client)
            retained = []
            retired = 0
            for page in pages:
                entry = self._entry(page)
                if len(retained) >= limit and not entry.feedback:
                    client.pages.update(page_id=page["id"], archived=True)
                    retired += 1
                else:
                    retained.append(entry)
        self.logger.info("Discovery Pool refreshed: new=%d updated=%d retained=%d retired=%d.", created, updated, len(retained), retired)
        return retained

    @trace_call("component", "discovery_pool.update_presentations")
    def update_presentations(self, candidates: list[PaperCandidate]) -> None:
        """Localize existing display text while preserving feedback and cache dates.

        Args:
            candidates: Existing identities with translated display fields. Original
                titles, URLs, selection, preference marks and discovery dates remain.
        """
        self.logger.info("Updating Chinese discovery presentations: entries=%d.", len(candidates))
        with Client(auth=self.settings.token) as client:
            known = {entry.candidate.id: entry for entry in (self._entry(p) for p in self._query(client))}
            for candidate in candidates:
                entry = known[candidate.id]
                if (candidate.title, candidate.url) != (entry.candidate.title, entry.candidate.url):
                    raise ValueError("Presentation update changed the original source identity")
                client.pages.update(page_id=entry.page_id, properties=presentation(candidate))
                body = client.pages.retrieve_markdown(page_id=entry.page_id)
                if body.get("truncated"):
                    self.logger.warning("Pool body is partial; translated display properties were saved: title=%r.", candidate.title)
                    continue
                updates = []
                for old, new in (
                    (entry.candidate.summary, candidate.summary),
                    ("Source:", "原文来源："),
                    ("Discovery metadata; not a complete reading.", "发现线索，仅作速览；尚未完成精读。"),
                ):
                    if old and old != new and old in body["markdown"]:
                        updates.append({"old_str": old, "new_str": new})
                if updates:
                    client.pages.update_markdown(page_id=entry.page_id, type="update_content",
                                                 update_content={"content_updates": updates})
                if candidate.title not in body["markdown"]:
                    client.pages.update_markdown(page_id=entry.page_id, type="insert_content",
                                                 insert_content={"content": f"原标题：{candidate.title}\n\n", "position": {"type": "start"}})
        self.logger.info("Chinese discovery presentations saved: entries=%d.", len(candidates))

    @trace_call("component", "discovery_pool.mark_selected")
    def mark_selected(self, entry: DiscoveryEntry) -> None:
        """Record a successful selection while preserving feedback and source data."""
        with Client(auth=self.settings.token) as client:
            client.pages.update(page_id=entry.page_id, properties={"State": {"select": {"name": "Selected"}}})
        self.logger.info("Discovery selected: title=%r.", entry.candidate.title)
