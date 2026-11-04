"""Publish organized paper and knowledge briefs while retaining human notes."""

from collections.abc import Mapping
import hashlib

from notion_client import Client

from assistant.components.captures.models import CaptureBrief, CaptureReceipt, RawCapture
from assistant.components.captures.protocol import CapturePublisherProtocol
from logger import get_logger, trace_call
from plugins._shared.notion.config import CaptureSettings
from plugins._shared.notion.markdown import page_markdown
from plugins._shared.notion.schema import ensure_rich_text, ensure_checkbox

BRIEF_START = "## Assistant brief"
BRIEF_END = "## End of assistant brief"


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


class CapturePublisher(CapturePublisherProtocol):
    """Publish one source-linked brief while preserving human-owned page content."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind organized destination settings without opening a connection.

        Args:
            options: Notion settings from YAML.
        """
        self.settings = CaptureSettings.model_validate(options)
        self.logger = get_logger("plugins.captures.notion.publisher")

    @trace_call("component", "captures.publish")
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
        # Source identity locates the page; the receipt identifies this exact
        # source version and report. Neither depends on Notion's Markdown export.
        publication_key = "brief:" + hashlib.sha256(section.encode()).hexdigest()
        self.logger.info(
            'kind=script provider=notion Publishing organized capture: title=%r destination=%s evidence=%s.',
            brief.title,
            brief.destination,
            brief.evidence_level,
            extra={"details": {'source_page': capture.page_id}},
        )
        with Client(auth=self.settings.token) as client:
            source = client.data_sources.retrieve(data_source_id=data_source_id)
            title_name = next(name for name, value in source["properties"].items() if value["type"] == "title")
            bibliographic_properties = {}
            if brief.destination == "papers":
                # Matching URI/DOI links a re-imported source to its existing brief.
                matches, bibliographic_properties = self._bibliographic_matches(capture, source["properties"])
                page_filter["or"].extend(matches)
            response = client.data_sources.query(data_source_id=data_source_id, filter=page_filter, page_size=2)
            self.logger.debug(
                'kind=script provider=notion Organized-output lookup: matches=%d.',
                len(response['results']),
                extra={"details": {'source_page': capture.page_id}},
            )
            if len(response["results"]) > 1:
                raise ValueError(f"Multiple organized outputs for source {capture.url}")

            reading_properties = {}
            if brief.destination == "papers":
                existing_properties = response["results"][0]["properties"] if response["results"] else {}
                reading_properties = self._reading_properties(capture, brief, source["properties"], existing_properties)

            if response["results"]:
                existing = response["results"][0]
                page_id = existing["id"]
                confirmed = self._publication_key(existing) == publication_key
                if confirmed:
                    self.logger.info(
                        'kind=checkpoint Organized brief already confirmed: title=%r; preserving human notes.',
                        brief.title,
                        extra={"details": {"page": page_id}},
                    )
                else:
                    self.logger.debug(
                        'kind=script provider=notion Updating assistant brief: title=%r; human title and notes retained.',
                        brief.title,
                        extra={"details": {'page': page_id}},
                    )
                    body = page_markdown(client, page_id)
                    self._update_brief(client, page_id, body, section)
            else:
                self.logger.debug("kind=script provider=notion Creating organized %s page.", brief.destination,
                                  extra={"details": {"source_page": capture.page_id}})
                properties = {
                    title_name: {"title": rich_text(brief.title)},
                    property_name: property_value,
                    **bibliographic_properties,
                    **reading_properties,
                }
                if brief.destination == "papers":
                    properties["Source Type"] = {"select": {"name": capture.metadata.get("Source Type") or ("Zotero" if capture.kind == "notero" else "SimpRead")}}
                page = client.pages.create(
                    parent={"type": "data_source_id", "data_source_id": data_source_id},
                    properties=properties, markdown=section,
                )
                page_id = page["id"]
                confirmed = False

            # Confirm only after the body API succeeds. Lost acknowledgements
            # reuse the same page, and a matching receipt never rewrites content.
            if not confirmed:
                properties = {
                    property_name: property_value,
                    "Publication Key": {"rich_text": rich_text(publication_key)},
                }
                if brief.destination == "papers":
                    properties["Brief Status"] = {"select": {"name": "Reviewed"}}
                client.pages.update(page_id=page_id, properties=properties)
            # Fill missing reading fields even when the body was already confirmed.
            # Nonempty human-edited fields are deliberately preserved.
            if response["results"] and reading_properties:
                self.logger.info('Completing paper reading metadata: title=%r fields=%s.',
                                 brief.title, ", ".join(reading_properties))
                client.pages.update(page_id=page_id, properties=reading_properties)
            self.logger.debug(
                'kind=script provider=notion Verifying organized capture readback: destination=%s.',
                brief.destination,
                extra={"details": {'page': page_id}},
            )
            verified = client.pages.retrieve(page_id=page_id)
            if self._publication_key(verified) != publication_key:
                self.logger.error(
                    'kind=script provider=notion Organized capture confirmation failed: title=%r.',
                    brief.title,
                    extra={"details": {'page': page_id}},
                )
                raise ValueError(f"Brief publication key readback failed: {page_id}")
            receipt = CaptureReceipt(page_id=page_id, url=verified["url"], key=key, fingerprint=capture.fingerprint)
            if capture.kind == "notero" and brief.destination == "papers":
                # Confirm the destination first, including on publication retries.
                self.logger.info('Marking Notero entry as published to Papers: title=%r.', capture.title)
                client.pages.update(page_id=capture.page_id,
                                    properties={"Agent In Papers": {"checkbox": True}})
                source = client.pages.retrieve(page_id=capture.page_id)
                if not source["properties"]["Agent In Papers"]["checkbox"]:
                    raise ValueError(f"Notero Papers flag readback failed: {capture.page_id}")
                self.logger.info('Notero Papers flag verified: title=%r.', capture.title)
        self.logger.info(
            'kind=script provider=notion Organized capture readback verified: title=%r destination=%s.',
            brief.title,
            brief.destination,
            extra={"details": {'page': page_id, 'url': receipt.url}},
        )
        return receipt

    def _publication_key(self, page: dict) -> str:
        """Read a publication receipt independently of page Markdown.

        Args:
            page: Destination properties returned by a query or retrieval.

        Returns:
            Report receipt, or an empty string for an unconfirmed page.
        """
        fragments = page["properties"].get("Publication Key", {}).get("rich_text", [])
        key = "".join(fragment["plain_text"] for fragment in fragments)
        return key

    @trace_call("component", "captures.initialize_schema")
    def initialize_schema(self) -> None:
        """Add destination receipts and the visible Notero publication flag."""
        destinations = {self.settings.papers_data_source_id, self.settings.knowledge_data_source_id}
        with Client(auth=self.settings.token) as client:
            for data_source_id in sorted(destinations - {""}):
                ensure_rich_text(client, data_source_id, "Publication Key")
            if self.settings.papers_data_source_id:
                ensure_rich_text(client, self.settings.papers_data_source_id, "Reading Summary")
            if self.settings.notero_data_source_id:
                ensure_checkbox(client, self.settings.notero_data_source_id, "Agent In Papers")

    def _reading_properties(self, capture: RawCapture, brief: CaptureBrief,
                            schema: dict, existing: dict) -> dict:
        """Fill empty reading properties while preserving human-owned values.

        Args:
            capture: Original source metadata.
            brief: Evidence-grounded reading metadata.
            schema: Available destination property definitions.
            existing: Current destination values, or an empty mapping on creation.

        Returns:
            Nonempty supported property updates, excluding citation metadata.
        """
        metadata = capture.metadata
        reading = brief.reading
        source_tags = metadata.get("Collections", []) + metadata.get("Tags", [])
        source_tags = [tag for tag in source_tags if isinstance(tag, str)
                       and tag.strip().lower() not in {"ai-processed", "notion"}]
        values = {
            "Original Title": capture.title,
            "Authors": metadata.get("Authors"),
            "Abstract": metadata.get("Abstract") or reading.abstract,
            "Reading Summary": reading.summary,
            "Date": metadata.get("Date") or reading.publication_date,
            "Publication": metadata.get("Publication") or metadata.get("Proceedings Title") or reading.publication,
            "Year": metadata.get("Year"),
            "Keywords": reading.keywords or metadata.get("Keywords"),
            "Tags": source_tags or reading.tags,
            "Link": metadata.get("URL") or metadata.get("Link"),
            "Code": metadata.get("Code") or reading.code_url,
        }
        properties = {}
        for name, value in values.items():
            if not value or name not in schema:
                continue
            kind = schema[name]["type"]
            if existing.get(name, {}).get(kind):
                continue
            if kind == "rich_text" and isinstance(value, str):
                properties[name] = {kind: rich_text(value)}
            elif kind == "number" and isinstance(value, (int, float)):
                properties[name] = {kind: value}
            elif kind == "url" and isinstance(value, str) and value.startswith(("https://", "http://")):
                properties[name] = {kind: value}
            elif kind == "multi_select" and isinstance(value, list):
                names = list(dict.fromkeys(v.strip() for v in value if isinstance(v, str) and v.strip()))
                names = [v for v in names if v.lower() not in {"ai-processed", "notion"}]
                if names:
                    properties[name] = {kind: [{"name": v.replace(",", ";")[:100]} for v in names[:20]]}
        return properties

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
            self.logger.debug(
                'kind=script provider=notion Appending assistant brief to existing page.',
                extra={"details": {'page': page_id}},
            )
            client.pages.update_markdown(
                page_id=page_id, type="insert_content",
                insert_content={"content": "\n\n" + section, "position": {"type": "end"}},
            )
            return
        if body.count(BRIEF_START) != 1 or body.count(BRIEF_END) != 1:
            raise ValueError(f"Ambiguous assistant brief boundaries: {page_id}")
        self.logger.debug(
            'kind=script provider=notion Replacing assistant-owned brief region.',
            extra={"details": {'page': page_id}},
        )
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
