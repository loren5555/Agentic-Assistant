"""Read priorities and publish evidence-backed recommendations with stable keys."""

from collections.abc import Mapping
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

from notion_client import Client
from pydantic import BaseModel

from assistant.schemas.recommendation import PaperCandidate, Recommendation, ResearchInterest


class ResearchFeedSettings(BaseModel):
    """Configure existing research databases and their user-visible columns.

    Attributes:
        token: Integration token, never included in reports.
        research_interests_data_source_id: Read-only priorities.
        research_feed_data_source_id: Recommendation destination.
        inbox_data_source_id: Interested-feedback follow-up destination.
        interests_status_property: Existing interest select/status column.
        interests_active_value: Value identifying active interests.
        feed_category_property: Existing recommendation category column.
        feed_feedback_property: Human-maintained feedback column.
    """

    token: str
    research_interests_data_source_id: str = "48f7a170-0249-4c12-aa37-0c33c54f06cc"
    research_feed_data_source_id: str = "ba262e5f-d58d-4f63-a77a-1f27e72b087e"
    inbox_data_source_id: str
    interests_status_property: str = "Status"
    interests_active_value: str = "Active"
    feed_category_property: str = "Type"
    feed_feedback_property: str = "Human Feedback"


class ResearchFeed:
    """Own verified feed writes while preserving interests and human feedback."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind connection and property settings without network activity.

        Args:
            options: Notion configuration mapping.
        """
        self.settings = ResearchFeedSettings.model_validate(options)

    def initialize_schema(self) -> None:
        """Explicitly add stable write keys; do not remove existing properties."""
        with Client(auth=self.settings.token) as client:
            for source_id, name in ((self.settings.inbox_data_source_id, "Research Feed Key"),):
                source = client.data_sources.retrieve(data_source_id=source_id)
                if name not in source["properties"]:
                    client.data_sources.update(data_source_id=source_id,
                                               properties={name: {"rich_text": {}}})
                    verified = client.data_sources.retrieve(data_source_id=source_id)
                    if verified["properties"][name]["type"] != "rich_text":
                        raise ValueError(f"Follow-up schema readback failed: {source_id}")

    def read_active_interests(self) -> list[ResearchInterest]:
        """Read active interests without changing any priority or feedback.

        Returns:
            Priorities including their complete current Markdown descriptions.
        """
        settings = self.settings
        with Client(auth=settings.token) as client:
            source = client.data_sources.retrieve(data_source_id=settings.research_interests_data_source_id)
            kind = source["properties"][settings.interests_status_property]["type"]
            condition = {"property": settings.interests_status_property,
                         kind: {"equals": settings.interests_active_value}}
            pages = self._query(client, settings.research_interests_data_source_id, condition)
            interests = []
            for page in pages:
                description = self._body(client, page["id"])
                interests.append(ResearchInterest(id=page["id"], title=self._title(page),
                                                  description=description))
        return interests

    def publish(self, recommendation: Recommendation, key: str) -> str:
        """Publish a real qualified recommendation and verify its readable body.

        Args:
            recommendation: Candidate, primary evidence, and grounded assessment.
            key: Stable identity chosen by the workflow.

        Returns:
            Verified recommendation URL.
        """
        candidate = recommendation.candidate
        evidence = recommendation.evidence
        assessment = recommendation.assessment
        if candidate.demo or candidate.url.startswith("demo:"):
            raise ValueError("Synthetic discovery must never be published to Research Feed")
        if not assessment.qualified or assessment.category is None:
            raise ValueError("Only qualified recommendations can be published")
        if not evidence.primary_source or not evidence.text.strip():
            raise ValueError("Publication requires accessible primary evidence")
        if assessment.category == "Mainline Deep Read" and not evidence.full_text:
            raise ValueError("Mainline Deep Read requires complete primary text")

        sections = [f"Source: {candidate.url}", f"Evidence: {evidence.source_url}",
                    f"Reading scope: {'full text' if evidence.full_text else 'partial text'}",
                    f"Reason: {assessment.reason}"]
        for heading, points in (
            ("Author claims", assessment.author_claims),
            ("Experimental support", assessment.experimental_support),
            ("Agent inference", assessment.agent_inference),
        ):
            sections.append(f"## {heading}\n\n" + "\n".join(f"- {point}" for point in points))
        sections.append(f"Publication key: {key}")
        body = "\n\n".join(sections)
        settings = self.settings
        with Client(auth=settings.token) as client:
            source = client.data_sources.retrieve(data_source_id=settings.research_feed_data_source_id)
            title_name = self._title_name(source)
            category_kind = source["properties"][settings.feed_category_property]["type"]
            properties = {
                title_name: {"title": self._rich_text(candidate.title)},
                "Stable ID": {"rich_text": self._rich_text(key)},
                settings.feed_category_property: {category_kind: {"name": assessment.category}},
                "Recommendation Date": {"date": {"start": datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()}},
            }
            if "Canonical URL" in source["properties"]:
                properties["Canonical URL"] = {"url": candidate.url}
            if candidate.doi and "DOI" in source["properties"]:
                doi_kind = source["properties"]["DOI"]["type"]
                if doi_kind == "rich_text":
                    properties["DOI"] = {"rich_text": self._rich_text(candidate.doi)}
            condition = {"property": "Stable ID", "rich_text": {"equals": key}}
            matches = self._query(client, settings.research_feed_data_source_id, condition)
            if matches:
                page_id = matches[0]["id"]
            else:
                page = client.pages.create(
                    parent={"type": "data_source_id", "data_source_id": settings.research_feed_data_source_id},
                    properties=properties, markdown=body,
                )
                page_id = page["id"]
            url = self._verify(client, page_id, "Stable ID", key, candidate.title, body)
        return url

    def list_interested(self) -> list[dict[str, str]]:
        """Read Interested feedback without clearing or changing it.

        Returns:
            Feed page IDs, titles, and URLs for follow-up dispatch.
        """
        settings = self.settings
        with Client(auth=settings.token) as client:
            source = client.data_sources.retrieve(data_source_id=settings.research_feed_data_source_id)
            kind = source["properties"][settings.feed_feedback_property]["type"]
            condition = {"property": settings.feed_feedback_property, kind: {"equals": "Interested"}}
            pages = self._query(client, settings.research_feed_data_source_id, condition)
            records = [{"id": page["id"], "title": self._title(page), "url": page["url"]}
                       for page in pages]
        return records

    def find_existing(self, candidate: PaperCandidate) -> str | None:
        """Find historical recommendations without reading every feed page.

        Args:
            candidate: Real candidate identity and optional DOI.

        Returns:
            Existing recommendation URL or None when no identity matches.
        """
        settings = self.settings
        with Client(auth=settings.token) as client:
            source = client.data_sources.retrieve(data_source_id=settings.research_feed_data_source_id)
            normalized = candidate.doi.strip().lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:").strip()
            identity = f"doi:{normalized}" if normalized else candidate.id
            stable_key = hashlib.sha256(f"research-feed:{identity}".encode()).hexdigest()
            clauses = [
                {"property": "Stable ID", "rich_text": {"equals": value}}
                for value in {candidate.id, identity, stable_key}
            ]
            if "Canonical URL" in source["properties"]:
                clauses.append({"property": "Canonical URL", "url": {"equals": candidate.url}})
            if candidate.doi and "DOI" in source["properties"]:
                normalized = candidate.doi.lower().removeprefix("https://doi.org/").removeprefix("doi:").strip()
                doi_kind = source["properties"]["DOI"]["type"]
                for value in (normalized, f"https://doi.org/{normalized}", f"doi:{normalized}", candidate.doi):
                    clauses.append({"property": "DOI", doi_kind: {"equals": value}})
            matches = self._query(client, settings.research_feed_data_source_id, {"or": clauses})
            url = matches[0]["url"] if matches else None
        return url

    def create_follow_up(self, feed_page_id: str) -> str:
        """Create one Inbox follow-up per Interested recommendation, never Papers.

        Args:
            feed_page_id: Reviewed feed page identity, also the stable follow-up key.

        Returns:
            Verified Inbox URL, or empty string if feedback is no longer Interested.
        """
        settings = self.settings
        with Client(auth=settings.token) as client:
            feed_page = client.pages.retrieve(page_id=feed_page_id)
            feedback = feed_page["properties"][settings.feed_feedback_property]
            selection = feedback[feedback["type"]]
            if selection is None or selection["name"] != "Interested":
                return ""
            # Honor follow-ups already created by the previous Inbox Intake workflow.
            old_status = feed_page["properties"].get("Inbox Status")
            if old_status is not None:
                old_value = old_status[old_status["type"]]
                if isinstance(old_value, dict) and old_value.get("name") == "Submitted":
                    return ""
            old_page = feed_page["properties"].get("Inbox Page")
            if old_page is not None and old_page[old_page["type"]]:
                return ""
            title = f"Read and discuss: {self._title(feed_page)}"
            body = (f"Human feedback: Interested\n\nSource recommendation: {feed_page['url']}\n\n"
                    f"Research Feed Key: {feed_page_id}")
            source = client.data_sources.retrieve(data_source_id=settings.inbox_data_source_id)
            condition = {"property": "Research Feed Key", "rich_text": {"equals": feed_page_id}}
            matches = self._query(client, settings.inbox_data_source_id, condition)
            if matches:
                page_id = matches[0]["id"]
            else:
                properties = {
                    self._title_name(source): {"title": self._rich_text(title)},
                    "Research Feed Key": {"rich_text": self._rich_text(feed_page_id)},
                }
                page = client.pages.create(
                    parent={"type": "data_source_id", "data_source_id": settings.inbox_data_source_id},
                    properties=properties, markdown=body,
                )
                page_id = page["id"]
            url = self._verify(client, page_id, "Research Feed Key", feed_page_id, title, body)
        return url

    def _query(self, client: Client, source_id: str, condition: dict) -> list[dict]:
        """Collect filtered pages while following Notion pagination.

        Args:
            client: Operation-owned client.
            source_id: Database data source.
            condition: SDK filter expression.

        Returns:
            Matching pages, not unfiltered database history.
        """
        arguments = {"data_source_id": source_id, "filter": condition, "page_size": 100}
        pages = []
        while True:
            response = client.data_sources.query(**arguments)
            pages.extend(response["results"])
            if not response["has_more"]:
                break
            arguments["start_cursor"] = response["next_cursor"]
        return pages

    def _body(self, client: Client, page_id: str) -> str:
        """Retrieve complete Markdown rather than silently using partial evidence.

        Args:
            client: Operation-owned client.
            page_id: Page identity.

        Returns:
            Complete Markdown body.
        """
        response = client.pages.retrieve_markdown(page_id=page_id)
        if response["truncated"] or response["unknown_block_ids"]:
            raise ValueError(f"Incomplete Markdown for {page_id}")
        body = response["markdown"]
        return body

    def _verify(self, client: Client, page_id: str, property_name: str,
                key: str, title: str, expected: str) -> str:
        """Re-fetch written identity and content before acknowledging publication.

        Args:
            client: Operation-owned client.
            page_id: Created or recovered page.
            property_name: Stable-key column.
            key: Expected key.
            title: Expected readable title.
            expected: Actual report written by this operation.

        Returns:
            Verified page URL.
        """
        page = client.pages.retrieve(page_id=page_id)
        stored_key = "".join(part["plain_text"] for part in page["properties"][property_name]["rich_text"])
        body = self._body(client, page_id)
        if stored_key != key or self._title(page) != title or " ".join(expected.split()) not in " ".join(body.split()):
            raise ValueError(f"Research publication readback failed: {page_id}")
        url = page["url"]
        return url

    def _title_name(self, source: dict) -> str:
        """Find the title property by type.

        Args:
            source: Data-source schema.

        Returns:
            User-visible title column name.
        """
        name = next(name for name, value in source["properties"].items() if value["type"] == "title")
        return name

    def _title(self, page: dict) -> str:
        """Extract a page title independently of its column name.

        Args:
            page: Notion page object.

        Returns:
            Plain title.
        """
        value = next(value for value in page["properties"].values() if value["type"] == "title")
        title = "".join(part["plain_text"] for part in value["title"])
        return title

    def _rich_text(self, text: str) -> list[dict]:
        """Split text into the SDK's bounded fragments.

        Args:
            text: Exact property content.

        Returns:
            Rich-text payload.
        """
        parts = [{"type": "text", "text": {"content": text[offset:offset + 2000]}}
                 for offset in range(0, len(text), 2000)]
        return parts
