"""Read source snapshots and store feedback on the same Notion record.

Input origin:
    Each processor owns one registered database and its eligibility rules.
Output destination:
    Shared SourceMaterial enters Organizer/Proposer; feedback is appended to
    assistant-owned source properties, without changing captured original text.
"""

from collections.abc import Mapping
import json

from notion_client import Client

from assistant.components.data.sources.models import SourceHistory, SourceMaterial
from assistant.components.data.sources.protocol import SourceProcessor
from logger import get_logger, trace_call
from plugins._shared.notion.markdown import page_markdown
from plugins._shared.notion.schema import ensure_checkbox, ensure_number, ensure_rich_text
from plugins._shared.notion.config import SourceCollectionSettings, ResearchFeedSettings
from assistant.runtime.records import digest


def rich_text(value: str) -> list[dict]:
    """Split assistant-owned text at Notion's fragment limit.

    Args:
        value: Text preserved verbatim.

    Returns:
        Notion rich-text fragments.
    """
    return [{"type": "text", "text": {"content": value[i:i + 2000]}} for i in range(0, len(value), 2000)]


def plain_text(prop: dict) -> str:
    """Read an optional text property.

    Args:
        prop: Notion rich-text or title property.

    Returns:
        Joined readable text.
    """
    return "".join(p.get("plain_text", p.get("text", {}).get("content", ""))
                   for p in prop.get(prop.get("type", "rich_text"), []))


class NotionProcessor(SourceProcessor):
    """Share storage mechanics while subclasses retain source selection rules."""

    kind = "inbox"

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind one source database without opening a connection.

        Args:
            options: Notion database IDs, source property names and batch limit.
        """
        self.options = dict(options)
        self.token = str(options["token"])
        capture = SourceCollectionSettings.model_validate(options)
        feed = ResearchFeedSettings.model_validate(options)
        self.data_source_id = {
            "inbox": options.get("inbox_data_source_id", ""),
            "todo": options.get("todo_data_source_id", ""),
            "notero": capture.notero_data_source_id,
            "simpread": capture.simpread_data_source_id,
            "paper": capture.papers_data_source_id,
            "feed": feed.research_feed_data_source_id,
            "interest": feed.research_interests_data_source_id,
        }[self.kind]
        self.limit = int(options.get("input_limit", 20))
        self.logger = get_logger(f"plugins.data.sources.{self.kind}")

    @trace_call("component", "processor.initialize_schema")
    def initialize_schema(self) -> None:
        """Prepare source context and completion properties without deleting fields."""
        if not self.data_source_id:
            return
        self.logger.info('Initializing source context: source=%s.', self.kind)
        with Client(auth=self.token) as client:
            ensure_number(client, self.data_source_id, "Agent Version")
            for name in ("Agent Feedback", "Agent History"):
                ensure_rich_text(client, self.data_source_id, name)
            ensure_checkbox(client, self.data_source_id, "Agent Processed")
            if self.kind in {"paper", "feed"}:
                ensure_checkbox(client, self.data_source_id, "Follow Up")
            if self.kind == "paper":
                ensure_checkbox(client, self.data_source_id, "Interested")
            elif self.kind == "interest":
                ensure_checkbox(client, self.data_source_id, "Agent Pending")
            elif self.kind == "simpread":
                ensure_checkbox(client, self.data_source_id, "Agent Archived")
        self.logger.info('Source context initialized: source=%s.', self.kind)

    def _filter(self, schema: dict) -> dict:
        """Select unconsumed work according to this source's own semantics.

        Args:
            schema: Current database property definitions.

        Returns:
            A server-side eligibility condition.
        """
        clauses = []
        # Native queues remain the human-facing authority. Reopening a consumed
        # Inbox/TODO/clip below advances its version instead of being ignored.
        if self.kind == "notero":
            clauses.append({"property": "Agent Processed", "checkbox": {"equals": False}})
        if self.kind in {"inbox", "todo"}:
            kind = schema["Status"]["type"]
            condition = {"does_not_equal": "Archived"} if self.kind == "inbox" else {"equals": "elevated"}
            clauses.append({"property": "Status", kind: condition})
        elif self.kind == "simpread":
            clauses.append({"property": "Agent Archived", "checkbox": {"equals": False}})
        elif self.kind == "paper":
            clauses.append({"property": "Follow Up", "checkbox": {"equals": True}})
        elif self.kind == "feed":
            clauses.append({"property": "Follow Up", "checkbox": {"equals": True}})
        elif self.kind == "interest":
            clauses.append({"property": "Agent Pending", "checkbox": {"equals": True}})
        return clauses[0] if len(clauses) == 1 else {"and": clauses}

    @trace_call("component", "processor.list_pending")
    def list_pending(self, page_id: str | None = None) -> list[SourceMaterial]:
        """Read a bounded batch, or an explicitly requested source.

        Args:
            page_id: Optional source page, independent of its queue status.

        Returns:
            Complete source snapshots with assistant context.
        """
        self.logger.info('Reading pending sources: source=%s explicit=%s.', self.kind, page_id is not None)
        with Client(auth=self.token) as client:
            if page_id:
                pages = [client.pages.retrieve(page_id=page_id)]
            else:
                schema = client.data_sources.retrieve(data_source_id=self.data_source_id)["properties"]
                pages = client.data_sources.query(
                    data_source_id=self.data_source_id, filter=self._filter(schema),
                    page_size=min(self.limit, 100), sorts=[{"timestamp": "created_time", "direction": "ascending"}],
                )["results"]
            sources = []
            for page in pages:
                source = self._read(client, page)
                if page_id is None and self.kind in {"inbox", "todo", "simpread", "interest", "paper", "feed"} and page["properties"].get("Agent Processed", {}).get("checkbox"):
                    source = self.apply_feedback(source, SourceHistory(
                        key=digest(f"reopened:{source.kind}:{source.page_id}:{source.version}:{source.revision}"),
                        workbench_url="", feedback="Reprocess requested by reopening the source queue.",
                    ))
                sources.append(source)
        self.logger.info('Pending sources read: source=%s count=%d.', self.kind, len(sources))
        return sources

    def _read(self, client: Client, page: dict) -> SourceMaterial:
        """Extract source content and separate assistant-owned context.

        Args:
            client: Connection owned by the current operation.
            page: Notion page with source properties.

        Returns:
            Effective source version; storage timestamps are not its identity.
        """
        parent = page["parent"].get("data_source_id", "").replace("-", "")
        if parent != str(self.data_source_id).replace("-", ""):
            raise ValueError(f"Page does not belong to {self.kind}: {page['id']}")
        title = ""
        metadata = {}
        props = page["properties"]
        for name, prop in props.items():
            kind = prop["type"]
            if kind == "title":
                title = plain_text(prop)
            elif name.startswith("Agent ") or name in {
                "Status", "Date Added", "Date Modified", "Publication Key", "Brief Status",
                "Citation Key", "In-Text Citation", "Full Citation", "File Path", "Extra",
                "Follow Up", "Interested", "Human Feedback",
            }:
                continue
            elif kind == "rich_text":
                metadata[name] = plain_text(prop)
            elif kind in {"url", "number", "checkbox"}:
                metadata[name] = prop.get(kind)
            elif kind in {"select", "status"}:
                metadata[name] = (prop.get(kind) or {}).get("name")
            elif kind == "multi_select":
                metadata[name] = [entry["name"] for entry in prop.get(kind, [])]
        self.logger.debug('Reading source body: title=%r source=%s.', title, self.kind,
                          extra={"details": {"page": page["id"]}})
        body = page_markdown(client, page["id"])
        self.logger.debug('Source body read: title=%r characters=%d.', title, len(body))
        text = "\n\n".join(part for part in [title, body] if part)
        history = plain_text(props.get("Agent History", {}))
        return SourceMaterial(
            kind=self.kind, page_id=page["id"], url=page["url"], title=title,
            text=text, metadata=metadata, revision=page["last_edited_time"],
            version=int(props.get("Agent Version", {}).get("number") or 1),
            supplement=plain_text(props.get("Agent Feedback", {})),
            history=[SourceHistory.model_validate(entry) for entry in json.loads(history or "[]")],
        )

    @trace_call("component", "processor.read")
    def read(self, source: SourceMaterial) -> SourceMaterial:
        """Refresh one source without imposing queue eligibility.

        Args:
            source: Original source identity.

        Returns:
            Current effective source.
        """
        with Client(auth=self.token) as client:
            return self._read(client, client.pages.retrieve(page_id=source.page_id))

    def _queue_properties(self, client: Client, pending: bool) -> dict:
        """Build source-specific queue updates.

        Args:
            client: Connection used for schema-aware status writes.
            pending: Whether to reopen rather than acknowledge the input.

        Returns:
            Assistant-owned flags and native source status updates.
        """
        props = {"Agent Processed": {"checkbox": not pending}}
        if self.kind in {"inbox", "todo"}:
            schema = client.data_sources.retrieve(data_source_id=self.data_source_id)["properties"]
            value = ("Pending" if pending else "Archived") if self.kind == "inbox" else ("elevated" if pending else "handled")
            props["Status"] = {schema["Status"]["type"]: {"name": value}}
        elif self.kind == "simpread":
            props["Agent Archived"] = {"checkbox": not pending}
        elif self.kind == "interest":
            props["Agent Pending"] = {"checkbox": pending}
        elif self.kind in {"paper", "feed"}:
            props["Follow Up"] = {"checkbox": pending}
        return props

    @trace_call("component", "processor.acknowledge")
    def acknowledge(self, source: SourceMaterial) -> None:
        """Consume only the version represented by the published proposal.

        Args:
            source: Successfully submitted source snapshot.
        """
        self.logger.info('Acknowledging input: title=%r source=%s version=%d.', source.title, self.kind, source.version)
        with Client(auth=self.token) as client:
            current = self._read(client, client.pages.retrieve(page_id=source.page_id))
            if current.fingerprint != source.fingerprint:
                raise RuntimeError("Source changed before acknowledgement")
            props = self._queue_properties(client, False)
            client.pages.update(page_id=source.page_id, properties=props)
            verified = client.pages.retrieve(page_id=source.page_id)
            if not verified["properties"]["Agent Processed"]["checkbox"]:
                raise ValueError("Source acknowledgement was not saved")
        self.logger.info('Input acknowledged: title=%r source=%s.', source.title, self.kind)

    @trace_call("component", "processor.apply_feedback")
    def apply_feedback(self, source: SourceMaterial, feedback: SourceHistory) -> SourceMaterial:
        """Reopen a new source version exactly once for one feedback round.

        Args:
            source: Scope of the work receiving human feedback.
            feedback: Stable feedback identity and historical deliverable.

        Returns:
            Reopened source, including retries after lost acknowledgements.
        """
        self.logger.info('Writing feedback to source: title=%r source=%s.', source.title, self.kind)
        with Client(auth=self.token) as client:
            current = self._read(client, client.pages.retrieve(page_id=source.page_id))
            if any(entry.key == feedback.key for entry in current.history):
                self.logger.info('Feedback already applied: title=%r version=%d.', current.title, current.version)
                return current
            history = [*current.history, feedback]
            supplement = "\n\n".join(part for part in [current.supplement, feedback.feedback] if part)
            version = current.version + 1
            props = self._queue_properties(client, True)
            props.update({"Agent Version": {"number": version},
                          "Agent Feedback": {"rich_text": rich_text(supplement)},
                          "Agent History": {"rich_text": rich_text(json.dumps([h.model_dump() for h in history], ensure_ascii=False))}})
            # Feedback, identity, version and reopening share one property update.
            client.pages.update(page_id=source.page_id, properties=props)
            verified = self._read(client, client.pages.retrieve(page_id=source.page_id))
            if verified.version != version or not any(h.key == feedback.key for h in verified.history):
                raise ValueError("Source feedback version was not saved")
        self.logger.info('Source reopened: title=%r version=%d.', verified.title, verified.version)
        return verified


class InboxProcessor(NotionProcessor):
    """Read unarchived human input and archive it after proposal submission."""

    kind = "inbox"


class TodoProcessor(NotionProcessor):
    """Read only human-elevated TODO items and mark consumed input handled."""

    kind = "todo"


class NoteroProcessor(NotionProcessor):
    """Read original papers while preserving Zotero-managed metadata."""

    kind = "notero"


class SimpReadProcessor(NotionProcessor):
    """Use Agent Archived as the visible clipping-consumption flag."""

    kind = "simpread"


class PaperProcessor(NotionProcessor):
    """Read papers explicitly marked Follow Up as new information signals."""

    kind = "paper"


class FeedProcessor(NotionProcessor):
    """Read explicit recommendation follow-ups without creating an Inbox copy."""

    kind = "feed"


class InterestProcessor(NotionProcessor):
    """Read explicit Agent Pending requests, not every active recommendation interest."""

    kind = "interest"
