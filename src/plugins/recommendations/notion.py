"""Read priorities and publish evidence-backed recommendations with stable keys."""

from collections.abc import Mapping
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib

from notion_client import Client

from assistant.components.recommendations.identity import candidate_identity
from assistant.components.recommendations.models import PaperCandidate, Recommendation, ResearchInterest
from logger import get_logger, trace_call
from plugins._shared.notion.config import ResearchFeedSettings
from plugins._shared.notion.schema import ensure_rich_text


class ResearchFeed:
    """Own verified feed writes while preserving interests and human feedback."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind connection and property settings without network activity.

        Args:
            options: Notion configuration mapping.
        """
        self.settings = ResearchFeedSettings.model_validate(options)
        self.logger = get_logger("plugins.recommendations.notion")

    @trace_call("component", "recommendations.initialize_schema")
    def initialize_schema(self) -> None:
        """Explicitly add stable write keys; do not remove existing properties."""
        with Client(auth=self.settings.token) as client:
            ensure_rich_text(client, self.settings.research_feed_data_source_id, "Stable ID")

    @trace_call("component", "recommendations.read_active_interests")
    def read_active_interests(self) -> list[ResearchInterest]:
        """Read active interests without changing any priority or feedback.

        Returns:
            Priorities including their complete current Markdown descriptions.
        """
        settings = self.settings
        self.logger.info(
            'kind=script provider=notion Reading research interests: active_value=%s.',
            settings.interests_active_value,
            extra={"details": {'property': settings.interests_status_property}},
        )
        with Client(auth=settings.token) as client:
            source = client.data_sources.retrieve(data_source_id=settings.research_interests_data_source_id)
            kind = source["properties"][settings.interests_status_property]["type"]
            condition = {"property": settings.interests_status_property,
                         kind: {"equals": settings.interests_active_value}}
            pages = self._query(client, settings.research_interests_data_source_id, condition)
            interests = []
            for position, page in enumerate(pages, start=1):
                self.logger.debug(
                    'kind=script provider=notion Reading interest body %d/%d.',
                    position,
                    len(pages),
                    extra={"details": {'page': page['id']}},
                )
                description = self._body(client, page["id"])
                interests.append(ResearchInterest(id=page["id"], title=self._title(page),
                                                  description=description))
        self.logger.info("kind=script provider=notion Active research interests read: pages=%d.", len(interests))
        return interests

    @trace_call("component", "recommendations.read_interested_papers")
    def read_interested_papers(self) -> list[ResearchInterest]:
        """Read persistent paper preferences independently of proposal intake.

        Returns:
            Interested paper notes used as research preference context only.
        """
        self.logger.info("Reading Interested Papers as recommendation preferences.")
        with Client(auth=self.settings.token) as client:
            pages = self._query(client, self.settings.papers_data_source_id,
                                {"property": "Interested", "checkbox": {"equals": True}})
            preferences = [ResearchInterest(id=page["id"], title="Interested paper: " + self._title(page),
                                             description=self._body(client, page["id"])) for page in pages]
        self.logger.info("Paper preferences read: count=%d.", len(preferences))
        return preferences

    @trace_call("component", "recommendations.publish")
    def publish(self, recommendation: Recommendation, key: str) -> str:
        """Publish a real qualified recommendation and confirm its identity marker.

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
        self.logger.info(
            'kind=script provider=notion Publishing Research Feed entry: title=%r category=%s.',
            candidate.title, assessment.category,
            extra={"details": {'candidate': candidate.id}},
        )

        sections = [f"Source: {candidate.url}", f"Evidence: {evidence.source_url}",
                    f"Reading scope: {'full text' if evidence.full_text else 'partial text'}",
                    f"Reason: {assessment.reason}"]
        for heading, points in (
            ("Author claims", assessment.author_claims),
            ("Experimental support", assessment.experimental_support),
            ("Agent inference", assessment.agent_inference),
        ):
            sections.append(f"## {heading}\n\n" + "\n".join(f"- {point}" for point in points))
        if candidate.published_date:
            sections.append(f"Source publication date: {candidate.published_date}")
        sections.append(f"## Reading scope\n\n{evidence.reading_scope}")
        if evidence.summary:
            sections.append(f"## Reader synopsis (model-generated)\n\n{evidence.summary}")
        sections.append(f"## Source excerpts\n\n{evidence.text}")
        if evidence.limitations or evidence.failure:
            limitations = [*evidence.limitations, *([evidence.failure] if evidence.failure else [])]
            sections.append("## Reading limitations\n\n" + "\n".join(f"- {point}" for point in limitations))
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
                "Recommendation Date": {"date": {"start": (recommendation.day or datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())}},
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
                self.logger.info(
                    'kind=script provider=notion Recovering existing Research Feed publication.',
                    extra={"details": {'page': page_id}},
                )
            else:
                self.logger.info(
                    'kind=script provider=notion Creating Research Feed entry.',
                    extra={"details": {'candidate': candidate.id}},
                )
                page = client.pages.create(
                    parent={"type": "data_source_id", "data_source_id": settings.research_feed_data_source_id},
                    properties=properties, markdown=body,
                )
                page_id = page["id"]
            url = self._verify(client, page_id, "Stable ID", key, candidate.title)
        self.logger.info(
            'kind=script provider=notion Research Feed publication verified.',
            extra={"details": {'candidate': candidate.id, 'page': page_id, 'url': url}},
        )
        return url

    @trace_call("component", "recommendations.find_existing")
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
            identity = candidate_identity(candidate)
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
        query_number = 0
        self.logger.debug(
            'kind=script provider=notion Querying research collection.',
            extra={"details": {'data_source': source_id}},
        )
        self.logger.debug("kind=script provider=notion Research collection filter.",
                          extra={"details": {"filter": condition}})
        while True:
            response = client.data_sources.query(**arguments)
            pages.extend(response["results"])
            query_number += 1
            self.logger.debug("kind=script provider=notion Research query batch %d: returned=%d total=%d has_more=%s.",
                             query_number, len(response["results"]), len(pages), response["has_more"])
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
                key: str, title: str) -> str:
        """Confirm stable identity and the report marker after Notion normalization.

        Args:
            client: Operation-owned client.
            page_id: Created or recovered page.
            property_name: Stable-key column.
            key: Expected key.
            title: Expected readable title.

        Returns:
            Verified page URL.
        """
        page = client.pages.retrieve(page_id=page_id)
        stored_key = "".join(part["plain_text"] for part in page["properties"][property_name]["rich_text"])
        body = self._body(client, page_id)
        if stored_key != key or self._title(page) != title or key not in body:
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
