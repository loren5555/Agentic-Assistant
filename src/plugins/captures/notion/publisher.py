"""Publish organized paper and knowledge briefs while retaining human notes."""

from collections.abc import Mapping
import hashlib
import html
import re
from urllib.parse import urlsplit

from notion_client import Client

from assistant.components.captures.models import CaptureBrief, CaptureReceipt, RawCapture
from assistant.components.captures.protocol import CapturePublisherProtocol
from logger import get_logger
from plugins._shared.notion.config import CaptureSettings
from plugins._shared.notion.markdown import page_markdown

BRIEF_START = "## Assistant brief"
BRIEF_END = "## End of assistant brief"


def canonical_notion_url(match: re.Match[str]) -> str:
    """Compare Notion page links by page ID rather than display URL.

    Args:
        match: HTTP URL found in the Markdown being compared.

    Returns:
        Stable page reference for Notion pages, or the original external URL.
    """
    url = match.group(0)
    parsed = urlsplit(url)
    if parsed.hostname in {"notion.so", "www.notion.so", "notion.com", "www.notion.com", "app.notion.com"}:
        page_id = re.search(r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})$", parsed.path)
        if page_id:
            url = "notion-page:" + page_id.group(1).replace("-", "").lower()
    return url


def normalize_brief_markdown(content: str) -> str:
    """Normalize observed Notion export transformations, not missing content.

    Args:
        content: Generated or retrieved assistant-owned Markdown.

    Returns:
        Comparable text preserving words, external link targets, and order.
    """
    text = html.unescape(content)
    text = re.sub(r'<mention-page\s+url="([^"]+)"\s*/>', r"\1", text)
    # Export wraps bare URLs as links. Keep custom labels as well as targets,
    # so changing a citation's destination cannot pass as a formatting change.
    text = re.sub(
        r"\[([^\]\n]*)\]\((https?://[^\s)]+)\)",
        lambda match: match.group(2) if match.group(1) == match.group(2)
        else match.group(1) + " " + match.group(2),
        text,
    )
    text = re.sub(r'https?://[^\s<>"\])]+', canonical_notion_url, text)
    normalized = " ".join(text.split())
    return normalized


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
        self.logger.info("kind=script provider=notion Publishing organized capture: source_page=%s destination=%s evidence=%s.",
                         capture.page_id, brief.destination, brief.evidence_level)
        with Client(auth=self.settings.token) as client:
            source = client.data_sources.retrieve(data_source_id=data_source_id)
            title_name = next(name for name, value in source["properties"].items() if value["type"] == "title")
            bibliographic_properties = {}
            if brief.destination == "papers":
                # Matching URI/DOI links a re-imported source to its existing brief.
                matches, bibliographic_properties = self._bibliographic_matches(capture, source["properties"])
                page_filter["or"].extend(matches)
            response = client.data_sources.query(data_source_id=data_source_id, filter=page_filter, page_size=2)
            self.logger.debug("kind=script provider=notion Organized-output lookup: source_page=%s matches=%d.", capture.page_id, len(response["results"]))
            if len(response["results"]) > 1:
                raise ValueError(f"Multiple organized outputs for source {capture.url}")

            if response["results"]:
                page_id = response["results"][0]["id"]
                self.logger.debug("kind=script provider=notion Updating existing assistant brief: page=%s; human title and notes retained.", page_id)
                # Canonicalize only the assistant-owned provenance property.
                client.pages.update(page_id=page_id, properties={property_name: property_value})
                body = page_markdown(client, page_id)
                self._update_brief(client, page_id, body, section)
            else:
                self.logger.debug("kind=script provider=notion Creating organized %s page for source=%s.", brief.destination, capture.page_id)
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
            self.logger.debug("kind=script provider=notion Verifying organized capture readback: page=%s destination=%s.", page_id, brief.destination)
            verified = client.pages.retrieve(page_id=page_id)
            body = page_markdown(client, page_id)
            stored = verified["properties"][property_name]
            stored_identity = stored["url"] if brief.destination == "papers" else "".join(part["plain_text"] for part in stored["rich_text"])
            expected_identity = capture.url if brief.destination == "papers" else key
            self._verify_brief(page_id, body, section, stored_identity, expected_identity)
            if brief.destination == "papers" and verified["properties"]["Brief Status"]["select"]["name"] != "Reviewed":
                self.logger.error("kind=script provider=notion Organized capture verification failed: page=%s mismatches=brief_status.", page_id)
                raise ValueError(f"Brief status readback failed: {page_id}")
            receipt = CaptureReceipt(page_id=page_id, url=verified["url"], key=key, fingerprint=capture.fingerprint)
        self.logger.info("kind=script provider=notion Organized capture readback verified: destination=%s page=%s url=%s.",
                         brief.destination, page_id, receipt.url)
        return receipt

    def _verify_brief(
        self, page_id: str, body: str, section: str, stored_identity: str, expected_identity: str,
    ) -> None:
        """Check the complete owned report and its separate provenance property.

        Args:
            page_id: Destination page used in diagnostic logs.
            body: Complete readback including human notes.
            section: Expected assistant brief, evidence, reason, and source markers.
            stored_identity: Provenance property retrieved from Notion.
            expected_identity: Source URL or archive key submitted for publication.
        """
        mismatches = []
        if stored_identity != expected_identity:
            mismatches.append("source_property")

        if body.count(BRIEF_START) != 1 or body.count(BRIEF_END) != 1:
            mismatches.append("brief_boundaries")
        else:
            start = body.index(BRIEF_START)
            end = body.index(BRIEF_END) + len(BRIEF_END)
            if end <= start:
                mismatches.append("brief_boundary_order")
            else:
                actual = normalize_brief_markdown(body[start:end])
                expected = normalize_brief_markdown(section)
                if actual != expected:
                    mismatches.append("brief_content_or_provenance")

        if mismatches:
            details = ", ".join(mismatches)
            self.logger.error("kind=script provider=notion Organized capture verification failed: page=%s mismatches=%s.", page_id, details)
            raise ValueError(f"Brief publication readback failed: {page_id}; mismatches={details}")

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
            self.logger.debug("kind=script provider=notion Appending assistant brief to existing page: page=%s.", page_id)
            client.pages.update_markdown(
                page_id=page_id, type="insert_content",
                insert_content={"content": "\n\n" + section, "position": {"type": "end"}},
            )
            return
        if body.count(BRIEF_START) != 1 or body.count(BRIEF_END) != 1:
            raise ValueError(f"Ambiguous assistant brief boundaries: {page_id}")
        self.logger.debug("kind=script provider=notion Replacing assistant-owned brief region: page=%s.", page_id)
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
