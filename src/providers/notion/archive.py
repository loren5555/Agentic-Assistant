"""Publish retained outcomes without creating workflow or activity records."""

from collections.abc import Mapping

from notion_client import Client
from pydantic import BaseModel

from assistant.protocol.curator import ArchiveStoreProtocol
from assistant.schemas.curation import ArchiveReceipt, RetainedArtifact
from assistant.schemas.proposal import WorkbenchItem


class ArchiveSettings(BaseModel):
    """Configure the long-term databases independently from Workbench.

    Attributes:
        token: Notion integration token.
        knowledge_data_source_id: Destination for reusable knowledge.
        ideas_data_source_id: Destination for research ideas.
    """

    token: str
    knowledge_data_source_id: str = ""
    ideas_data_source_id: str = ""


class ArchiveStore(ArchiveStoreProtocol):
    """Own destination writes, provenance, and readback under stable keys.

    Attributes:
        settings: Destination connection settings.
        title_properties: Title-property names resolved on first use per data source.
    """

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind destination settings without making a Notion request.

        Args:
            options: Notion settings from YAML.
        """
        self.settings = ArchiveSettings.model_validate(options)
        self.title_properties: dict[str, str] = {}

    def initialize_schema(self) -> None:
        """Explicitly add Archive Key to configured destination databases.

        Empty destinations are skipped so zero-output tasks need no archive setup.
        """
        destinations = [self.settings.knowledge_data_source_id, self.settings.ideas_data_source_id]
        with Client(auth=self.settings.token) as client:
            for data_source_id in destinations:
                if not data_source_id:
                    continue
                source = client.data_sources.retrieve(data_source_id=data_source_id)
                if "Archive Key" not in source["properties"]:
                    client.data_sources.update(
                        data_source_id=data_source_id,
                        properties={"Archive Key": {"rich_text": {}}},
                    )

    def publish(
        self, item: WorkbenchItem, artifact: RetainedArtifact, key: str,
    ) -> ArchiveReceipt:
        """Save a retained outcome or recover its previous successful write.

        Args:
            item: Accepted task providing source and proposal version.
            artifact: Supported reusable outcome selected by Curator.
            key: Stable identifier persisted indirectly through the saved decision.

        Returns:
            Destination link after verifying its key, title, and page body.
        """
        destinations = {
            "knowledge": self.settings.knowledge_data_source_id,
            "idea": self.settings.ideas_data_source_id,
        }
        data_source_id = destinations[artifact.kind]
        if not data_source_id:
            raise ValueError(f"No Notion data source configured for {artifact.kind}")
        if item.proposal is None:
            raise ValueError("Retained outcomes require an originating proposal")

        content = (
            f"{artifact.content}\n\n## Provenance\n\n"
            f"Retention reason: {artifact.reason}\n\n"
            f"Workbench: {item.url}\n\nSource: {item.source_url}\n\n"
            f"Proposal version: {item.proposal.version}\n\nArchive key: {key}"
        )
        with Client(auth=self.settings.token) as client:
            title_property = self._title_property(client, data_source_id)
            response = client.data_sources.query(
                data_source_id=data_source_id,
                filter={"property": "Archive Key", "rich_text": {"equals": key}},
                page_size=1,
            )
            if response["results"]:
                page_id = response["results"][0]["id"]
            else:
                page = client.pages.create(
                    parent={"type": "data_source_id", "data_source_id": data_source_id},
                    properties={
                        title_property: {"title": self._rich_text(artifact.title)},
                        "Archive Key": {"rich_text": self._rich_text(key)},
                    },
                    markdown=content,
                )
                page_id = page["id"]

            # Re-fetch a created or recovered page before acknowledging publication.
            verified = client.pages.retrieve(page_id=page_id)
            properties = verified["properties"]
            stored_key = "".join(part["plain_text"] for part in properties["Archive Key"]["rich_text"])
            title = "".join(part["plain_text"] for part in properties[title_property]["title"])
            body = client.pages.retrieve_markdown(page_id=page_id)
            if (
                stored_key != key or title != artifact.title
                or body["truncated"] or body["unknown_block_ids"]
                or key not in body["markdown"]
            ):
                raise ValueError(f"Archive readback failed: {page_id}")
            receipt = ArchiveReceipt(key=key, url=verified["url"])
        return receipt

    def _title_property(self, client: Client, data_source_id: str) -> str:
        """Resolve a destination's title column once per store instance.

        Args:
            client: Client owned by the current publication.
            data_source_id: Destination database's data source.

        Returns:
            Property name used for the title, regardless of its user-visible name.
        """
        if data_source_id not in self.title_properties:
            source = client.data_sources.retrieve(data_source_id=data_source_id)
            title = next(
                name for name, property in source["properties"].items()
                if property["type"] == "title"
            )
            self.title_properties[data_source_id] = title
        name = self.title_properties[data_source_id]
        return name

    def _rich_text(self, text: str) -> list[dict]:
        """Split text into Notion's bounded rich-text fragments.

        Args:
            text: Value to preserve without changing its content.

        Returns:
            SDK rich-text fragments.
        """
        fragments = [
            {"type": "text", "text": {"content": text[offset:offset + 2000]}}
            for offset in range(0, len(text), 2000)
        ]
        return fragments
