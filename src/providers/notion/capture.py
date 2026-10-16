"""Read raw Notero/SimpRead captures and publish organized Notion briefs."""

import hashlib
from collections.abc import Mapping

from notion_client import Client
from pydantic import BaseModel

from assistant.protocol.capture import CapturePublisherProtocol, CaptureSourceProtocol
from assistant.schemas.capture import CaptureBatch, CaptureBrief, CaptureKind, CaptureReceipt, RawCapture


BRIEF_START = "## Assistant brief"
BRIEF_END = "## End of assistant brief"


class CaptureSettings(BaseModel):
    """Configure independent raw inputs and organized output collections.

    Attributes:
        token: Notion integration token.
        notero_data_source_id: Read-only Zotero-synced raw input.
        simpread_data_source_id: Independent article capture collection.
        papers_data_source_id: Organized paper briefs and human discussions.
        knowledge_data_source_id: Reusable explanations and methods.
    """

    token: str
    notero_data_source_id: str = "2f9835de-f60d-81f7-89e4-000bb7ff2dba"
    simpread_data_source_id: str = "1a9835de-f60d-8109-8b50-000b7d486414"
    papers_data_source_id: str = "3b8835de-f60d-835d-8c98-07c38b24fa6a"
    knowledge_data_source_id: str = ""


def rich_text(text: str) -> list[dict]:
    """Represent long text using Notion's bounded rich-text fragments.

    Args:
        text: Property content to preserve.

    Returns:
        SDK rich-text objects.
    """
    fragments = [
        {"type": "text", "text": {"content": text[offset:offset + 2000]}}
        for offset in range(0, len(text), 2000)
    ]
    return fragments


def page_markdown(client: Client, page_id: str) -> str:
    """Read complete page content rather than silently using an incomplete export.

    Args:
        client: Connection owned by the surrounding operation.
        page_id: Page to read.

    Returns:
        Complete captured Markdown.
    """
    response = client.pages.retrieve_markdown(page_id=page_id)
    if response["truncated"] or response["unknown_block_ids"]:
        raise ValueError(f"Incomplete capture Markdown: {page_id}")
    content = response["markdown"]
    return content


class CaptureSource(CaptureSourceProtocol):
    """Own raw capture reads and verified SimpRead completion writes."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind source connection settings without opening a connection.

        Args:
            options: Notion settings from YAML.
        """
        self.settings = CaptureSettings.model_validate(options)

    def list_captures(self, kind: CaptureKind, limit: int = 20, cursor: str | None = None) -> CaptureBatch:
        """Read one bounded query page so callers can persist continuation state.

        Args:
            kind: Notero or SimpRead input collection.
            limit: Maximum number of capture pages, between one and 100.
            cursor: Saved Notion pagination token.

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

        with Client(auth=self.settings.token) as client:
            response = client.data_sources.query(**arguments)
            captures = [self._read_capture(client, page, kind) for page in response["results"]]
        batch = CaptureBatch(captures=captures, next_cursor=response["next_cursor"])
        return batch

    def read_capture(self, page_id: str, kind: CaptureKind) -> RawCapture:
        """Retrieve the current source without modifying raw data.

        Args:
            page_id: Raw capture page identifier.
            kind: Expected raw collection.

        Returns:
            Current material and its meaningful-content fingerprint.
        """
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
            return
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
        return capture


class CapturePublisher(CapturePublisherProtocol):
    """Publish one source-linked brief while preserving human-owned page content."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind organized destination settings without opening a connection.

        Args:
            options: Notion settings from YAML.
        """
        self.settings = CaptureSettings.model_validate(options)

    def publish(self, capture: RawCapture, brief: CaptureBrief) -> CaptureReceipt:
        """Create or replace only the assistant-owned brief section.

        Args:
            capture: Source identity, actual evidence, and current content version.
            brief: Organized paper or knowledge content.

        Returns:
            Verified output identity and represented source version.
        """
        if brief.destination == "proposal":
            raise ValueError("Proposal captures must be submitted through Workbench")
        if brief.evidence_level == "full_text" and not capture.full_text_verified:
            raise ValueError(f"Full-text acquisition was not verified: {capture.url}")

        key = "capture:" + hashlib.sha256(capture.identity.encode()).hexdigest()
        data_source_id = self.settings.papers_data_source_id
        property_name = "Source Page"
        property_value = {"url": capture.url}
        # Notion app/web URLs can differ while referring to the same raw page.
        page_filter = {
            "or": [
                {"property": property_name, "url": {"equals": capture.url}},
                {"property": property_name, "url": {"contains": capture.page_id}},
                {"property": property_name, "url": {"contains": capture.page_id.replace("-", "")}},
            ],
        }
        if brief.destination == "knowledge":
            data_source_id = self.settings.knowledge_data_source_id
            property_name = "Archive Key"
            property_value = {"rich_text": rich_text(key)}
            page_filter = {"property": property_name, "rich_text": {"equals": key}}

        section = self._brief_section(capture, brief, key)
        with Client(auth=self.settings.token) as client:
            source = client.data_sources.retrieve(data_source_id=data_source_id)
            title_name = next(name for name, value in source["properties"].items() if value["type"] == "title")
            bibliographic_properties = {}
            if brief.destination == "papers":
                # Matching URI/DOI links a re-imported source to its existing brief.
                matches, bibliographic_properties = self._bibliographic_matches(capture, source["properties"])
                page_filter["or"].extend(matches)
            response = client.data_sources.query(data_source_id=data_source_id, filter=page_filter, page_size=2)
            if len(response["results"]) > 1:
                raise ValueError(f"Multiple organized outputs for source {capture.url}")

            if response["results"]:
                page_id = response["results"][0]["id"]
                # Canonicalize only the assistant-owned provenance property.
                client.pages.update(page_id=page_id, properties={property_name: property_value})
                body = page_markdown(client, page_id)
                self._update_brief(client, page_id, body, section)
            else:
                properties = {
                    title_name: {"title": rich_text(brief.title)},
                    property_name: property_value,
                    **bibliographic_properties,
                }
                if brief.destination == "papers":
                    properties["Source Type"] = {"select": {"name": "Zotero" if capture.kind == "notero" else "SimpRead"}}
                page = client.pages.create(
                    parent={"type": "data_source_id", "data_source_id": data_source_id},
                    properties=properties, markdown=section,
                )
                page_id = page["id"]

            # Updating an existing entry never overwrites its title or human notes.
            if brief.destination == "papers":
                client.pages.update(page_id=page_id, properties={"Brief Status": {"select": {"name": "Reviewed"}}})
            verified = client.pages.retrieve(page_id=page_id)
            body = page_markdown(client, page_id)
            stored = verified["properties"][property_name]
            stored_identity = stored["url"] if brief.destination == "papers" else "".join(part["plain_text"] for part in stored["rich_text"])
            expected_identity = capture.url if brief.destination == "papers" else key
            if (
                stored_identity != expected_identity or key not in body
                or capture.fingerprint not in body or brief.content not in body
                or f"Evidence read: {brief.evidence_level}" not in body
            ):
                raise ValueError(f"Brief publication readback failed: {page_id}")
            if brief.destination == "papers" and verified["properties"]["Brief Status"]["select"]["name"] != "Reviewed":
                raise ValueError(f"Brief status readback failed: {page_id}")
            receipt = CaptureReceipt(page_id=page_id, url=verified["url"], key=key, fingerprint=capture.fingerprint)
        return receipt

    def _bibliographic_matches(self, capture: RawCapture, schema: dict) -> tuple[list[dict], dict]:
        """Use available Zotero URI and DOI columns without inventing schema.

        Args:
            capture: Original bibliographic metadata.
            schema: Actual destination property definitions.

        Returns:
            Additional identity query clauses and properties for new entries.
        """
        values = {}
        for name, value in capture.metadata.items():
            normalized = name.lower().replace(" ", "").replace("_", "")
            if normalized in {"zoterouri", "doi"} and isinstance(value, str) and value:
                values[normalized] = value

        matches = []
        properties = {}
        for name, definition in schema.items():
            normalized = name.lower().replace(" ", "").replace("_", "")
            value = values.get(normalized)
            property_type = definition["type"]
            if value is None or property_type not in {"url", "rich_text"}:
                continue
            variants = [value]
            if normalized == "doi":
                doi = value.removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:").strip()
                variants = list(dict.fromkeys([value, doi, "https://doi.org/" + doi]))
                if property_type == "url":
                    value = "https://doi.org/" + doi
            for variant in variants:
                matches.append({"property": name, property_type: {"equals": variant}})
            properties[name] = {property_type: value if property_type == "url" else rich_text(value)}
        return matches, properties

    def _brief_section(self, capture: RawCapture, brief: CaptureBrief, key: str) -> str:
        """Render the only section owned by automated paper/article intake.

        Args:
            capture: Original provenance and content version.
            brief: Grounded organized report.
            key: Stable publication identity.

        Returns:
            Clearly bounded Markdown section.
        """
        section = (
            f"{BRIEF_START}\n\n{brief.content}\n\n"
            f"Evidence read: {brief.evidence_level}\n\nReason: {brief.reason}\n\n"
            f"Source: {capture.url}\n\nCapture key: {key}\n\n"
            f"Source fingerprint: {capture.fingerprint}\n\n{BRIEF_END}"
        )
        return section

    def _update_brief(self, client: Client, page_id: str, body: str, section: str) -> None:
        """Replace an exact owned region, never the entire destination page.

        Args:
            client: Connection owned by the publication operation.
            page_id: Destination page identifier.
            body: Current complete page Markdown.
            section: New assistant-owned report.
        """
        if BRIEF_START not in body and BRIEF_END not in body:
            client.pages.update_markdown(
                page_id=page_id, type="insert_content",
                insert_content={"content": "\n\n" + section, "position": {"type": "end"}},
            )
            return
        if body.count(BRIEF_START) != 1 or body.count(BRIEF_END) != 1:
            raise ValueError(f"Ambiguous assistant brief boundaries: {page_id}")
        start = body.index(BRIEF_START)
        end = body.index(BRIEF_END) + len(BRIEF_END)
        if end <= start:
            raise ValueError(f"Reversed assistant brief boundaries: {page_id}")
        old_section = body[start:end]
        if old_section != section:
            client.pages.update_markdown(
                page_id=page_id, type="update_content",
                update_content={"content_updates": [{"old_str": old_section, "new_str": section}]},
            )
