"""Read Inbox pages through the Notion SDK and convert them to input records."""

from collections.abc import Mapping

from notion_client import Client
from pydantic import BaseModel, ConfigDict

from assistant.schemas.inbox import InboxRecord
from assistant.protocol.inbox import InboxSourceProtocol


class NotionSettings(BaseModel):
    """Connection settings owned by the Notion provider.

    Attributes:
        token: Access token used to authenticate the SDK client.
        inbox_data_source_id: Inbox data source ID, not a database or page ID.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    token: str
    inbox_data_source_id: str


class InboxSource(InboxSourceProtocol):
    """Provide read-only access to individual Notion Inbox pages.

    Attributes:
        token: Access token used to open a client for each read operation.
        data_source_id: Inbox data source ID used to query the latest edited page.
    """

    def __init__(self, options: Mapping[str, object]):
        """Read provider settings without opening a client or making requests.

        Args:
            options: Notion connection settings from application configuration.
        """
        settings = NotionSettings.model_validate(options)
        self.token = settings.token
        self.data_source_id = settings.inbox_data_source_id

    def fetch_latest(self) -> InboxRecord | None:
        """Read the latest edited Inbox page without filtering or changing status.

        Returns:
            Input record containing the title, Markdown body, and page revision
            timestamp, or None if the data source has no queryable pages.
        """
        # Keep the query and body retrieval within one managed client lifetime.
        with Client(auth=self.token) as client:
            response = client.data_sources.query(
                data_source_id=self.data_source_id,
                page_size=1,
                result_type="page",
                sorts=[{"timestamp": "last_edited_time", "direction": "descending"}],
            )
            pages = response["results"]
            if not pages:
                return None

            # Query results include page properties; fetch only the missing body.
            record = self._read_record(client, pages[0])

        return record

    def fetch(self, source_id: str) -> InboxRecord:
        """Read a page by ID without checking membership in the Inbox data source.

        Args:
            source_id: ID of the Notion page to read.

        Returns:
            Input record containing the title, Markdown body, and page revision
            timestamp.
        """
        with Client(auth=self.token) as client:
            page = client.pages.retrieve(page_id=source_id)
            record = self._read_record(client, page)

        return record

    def _read_record(self, client: Client, page: dict) -> InboxRecord:
        """Fetch the body and convert Notion page data to an input record.

        Args:
            client: Active client owned by the current read operation.
            page: Full page object returned by a query or page retrieval, including
                id, last_edited_time, and properties. Properties must include a
                title-type property whose title text fragments contain plain_text.

        Returns:
            Input record with the title and body separated by a blank line, or an
            explicit empty-page placeholder if both are empty. The revision is
            the page's last_edited_time.
        """
        page_id = page["id"]
        content = client.pages.retrieve_markdown(page_id=page_id)

        # Reject incomplete content so downstream consumers cannot treat it as complete.
        if content["truncated"] or content["unknown_block_ids"]:
            raise ValueError(
                f"Notion page {page_id} has incomplete Markdown: "
                f"truncated={content['truncated']}, "
                f"unknown_block_ids={content['unknown_block_ids']}"
            )

        body = content["markdown"].strip()

        # Users can rename the title column, so identify it by type rather than name.
        title_property = next(
            value for value in page["properties"].values() if value["type"] == "title"
        )
        title = "".join(part["plain_text"] for part in title_property["title"]).strip()
        text = "\n\n".join(part for part in (title, body) if part)
        if not text:
            text = "(Untitled empty Notion page)"

        record = InboxRecord(
            source="notion",
            source_id=page_id,
            text=text,
            revision=page["last_edited_time"],
        )
        return record
