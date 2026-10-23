"""Read Notero and SimpRead raw captures."""

from collections.abc import Mapping

from notion_client import Client

from assistant.components.captures.models import CaptureBatch, CaptureKind, RawCapture
from assistant.components.captures.protocol import CaptureSourceProtocol
from logger import get_logger
from plugins._shared.notion.markdown import page_markdown
from plugins._shared.notion.config import CaptureSettings


class CaptureSource(CaptureSourceProtocol):
    """Own raw capture reads and verified SimpRead completion writes."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind source connection settings without opening a connection.

        Args:
            options: Notion settings from YAML.
        """
        self.settings = CaptureSettings.model_validate(options)
        self.logger = get_logger("plugins.captures.notion.source")

    def list_captures(
        self, kind: CaptureKind, limit: int = 20, cursor: str | None = None,
        handled_revisions: Mapping[str, str] | None = None,
    ) -> CaptureBatch:
        """Read pending bodies, checking handled Notero versions locally.

        Args:
            kind: Notero or SimpRead input collection.
            limit: Maximum number of pending capture bodies to return.
            cursor: Saved Notion pagination token.
            handled_revisions: Successfully handled source page versions.

        Returns:
            Raw captures and the next cursor, if another page exists.
        """
        arguments = {
            "data_source_id": self._source_id(kind), "page_size": min(limit, 100),
            "sorts": [{"timestamp": "created_time", "direction": "ascending"}],
        }
        if cursor is not None:
            arguments["start_cursor"] = cursor
        if kind == "simpread":
            arguments["filter"] = {"property": "Agent Archived", "checkbox": {"equals": False}}

        self.logger.info("kind=script provider=notion Querying raw captures: source=%s limit=%d continuing=%s filter=%s.",
                         kind, arguments["page_size"], cursor is not None,
                         "Agent Archived = false" if kind == "simpread" else "read-only Notero scan")
        handled_revisions = handled_revisions or {}
        captures = []
        skipped = 0
        with Client(auth=self.settings.token) as client:
            while True:
                # Bound the query by remaining capacity so no unconsumed rows
                # are lost when the resulting continuation token is saved.
                arguments["page_size"] = min(limit - len(captures), 100)
                response = client.data_sources.query(**arguments)
                pages = response["results"]
                self.logger.debug("kind=script provider=notion Raw capture query returned: source=%s pages=%d has_more=%s.",
                                 kind, len(pages), response["has_more"])
                for position, page in enumerate(pages, start=1):
                    # Notero stays read-only. A cheap properties query supplies
                    # the revision; unchanged pages need no markdown request.
                    if kind == "notero" and handled_revisions.get(page["id"]) == page["last_edited_time"]:
                        skipped += 1
                        continue
                    self.logger.debug("kind=script provider=notion Reading capture body %d/%d: source=%s page=%s.",
                                     position, len(pages), kind, page["id"])
                    captures.append(self._read_capture(client, page, kind))

                if len(captures) >= limit or not response["has_more"]:
                    break
                arguments["start_cursor"] = response["next_cursor"]
        batch = CaptureBatch(captures=captures, next_cursor=response["next_cursor"])
        self.logger.info("kind=script provider=notion Raw capture read completed: source=%s pending=%d unchanged_skipped=%d body_characters=%d.",
                         kind, len(captures), skipped, sum(len(capture.text) for capture in captures))
        return batch

    def read_capture(self, page_id: str, kind: CaptureKind) -> RawCapture:
        """Retrieve the current source without modifying raw data.

        Args:
            page_id: Raw capture page identifier.
            kind: Expected raw collection.

        Returns:
            Current material and its meaningful-content fingerprint.
        """
        self.logger.debug("kind=script provider=notion Refreshing raw capture: source=%s page=%s.", kind, page_id)
        with Client(auth=self.settings.token) as client:
            page = client.pages.retrieve(page_id=page_id)
            parent = page["parent"].get("data_source_id", "")
            if parent.replace("-", "") != self._source_id(kind).replace("-", ""):
                raise ValueError(f"Capture does not belong to {kind}: {page_id}")
            capture = self._read_capture(client, page, kind)
        return capture

    def mark_handled(self, capture: RawCapture) -> None:
        """Mark only SimpRead consumed after a verified downstream publication.

        Args:
            capture: Input whose output or proposal has been verified.
        """
        if capture.kind == "notero":
            self.logger.debug("kind=script provider=notion Notero acknowledgement skipped: read-only source page=%s.", capture.page_id)
            return
        self.logger.info("kind=script provider=notion Marking SimpRead handled after publication: page=%s.", capture.page_id)
        current = self.read_capture(capture.page_id, capture.kind)
        if current.fingerprint != capture.fingerprint:
            raise ValueError(f"Capture changed before completion: {capture.page_id}")
        with Client(auth=self.settings.token) as client:
            client.pages.update(
                page_id=capture.page_id,
                properties={"Agent Archived": {"checkbox": True}},
            )
            page = client.pages.retrieve(page_id=capture.page_id)
            if not page["properties"]["Agent Archived"]["checkbox"]:
                raise ValueError(f"Capture completion readback failed: {capture.page_id}")
        self.logger.info("kind=script provider=notion SimpRead Agent Archived verified: page=%s.", capture.page_id)

    def _source_id(self, kind: CaptureKind) -> str:
        """Select the configured raw collection.

        Args:
            kind: Input role.

        Returns:
            Notion data source ID.
        """
        source_id = self.settings.notero_data_source_id
        if kind == "simpread":
            source_id = self.settings.simpread_data_source_id
        return source_id

    def _read_capture(self, client: Client, page: dict, kind: CaptureKind) -> RawCapture:
        """Extract content without revision timestamps or agent bookkeeping.

        Args:
            client: Connection owned by the current read.
            page: Raw Notion page object.
            kind: Raw collection role.

        Returns:
            Captured material; attachment references remain references, not full text.
        """
        title = ""
        metadata = {}
        for name, property_value in page["properties"].items():
            property_type = property_value["type"]
            value = property_value.get(property_type)
            if property_type == "title":
                title = "".join(part["plain_text"] for part in value)
            elif (
                name.startswith("Agent ")
                or name.lower().strip() in {"date added", "date modified"}
                or property_type in {"created_time", "last_edited_time", "created_by", "last_edited_by"}
            ):
                continue
            elif property_type == "rich_text":
                metadata[name] = "".join(part["plain_text"] for part in value)
            elif property_type in {"select", "status"}:
                metadata[name] = value["name"] if value else None
            elif property_type == "multi_select":
                metadata[name] = [entry["name"] for entry in value]
            elif property_type == "files":
                # Signed file URLs expire independently of the source content.
                metadata[name] = [
                    {"name": entry["name"], "url": entry.get("external", {}).get("url")}
                    for entry in value
                ]
            elif property_type in {"url", "number", "checkbox", "date", "relation"}:
                metadata[name] = value
        body = page_markdown(client, page["id"])
        capture = RawCapture(
            kind=kind, page_id=page["id"], url=page["url"], title=title,
            text=body, metadata=metadata, revision=page["last_edited_time"],
        )
        self.logger.debug("kind=script provider=notion Capture body read: source=%s page=%s characters=%d metadata_fields=%d full_text_verified=%s.",
                          kind, capture.page_id, len(body), len(metadata), capture.full_text_verified)
        return capture
