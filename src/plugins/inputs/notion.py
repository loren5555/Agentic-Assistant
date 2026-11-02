"""Read Inbox/TODO material and acknowledge verified submissions."""

from collections.abc import Mapping
from typing import Literal
from urllib.parse import urlsplit
import re

from notion_client import Client

from assistant.components.inputs.models import SourceMaterial
from assistant.components.inputs.protocol import InputSourceProtocol
from logger import get_logger, trace_call
from plugins._shared.notion.config import NotionSettings


class InputSource(InputSourceProtocol):
    """Own source connections and input completion writes."""

    def __init__(self, options: Mapping[str, object]):
        """Read configuration without making a Notion request.

        Args:
            options: Notion connection and data source settings.
        """
        self.settings = NotionSettings.model_validate(options)
        self.logger = get_logger("plugins.inputs.notion")

    @trace_call("component", "inputs.list_inputs")
    def list_inputs(self) -> list[SourceMaterial]:
        """Read a bounded batch of unarchived Inbox and elevated TODO items.

        Returns:
            Source materials with page properties and complete Markdown bodies.
        """
        self.logger.info("kind=script provider=notion Reading Notion intake: Inbox Status != Archived; TODO Status = elevated; limit=%d per collection.",
                         self.settings.input_limit)
        with Client(auth=self.settings.token) as client:
            inbox_pages = self._query_pages(
                client,
                self.settings.inbox_data_source_id,
                {"property": "Status", "select": {"does_not_equal": "Archived"}},
                limit=self.settings.input_limit,
            )
            todo_pages = self._query_pages(
                client,
                self.settings.todo_data_source_id,
                {"property": "Status", "select": {"equals": "elevated"}},
                limit=self.settings.input_limit,
            )
            self.logger.debug("kind=script provider=notion Intake queries returned: inbox=%d todo=%d; reading page bodies.", len(inbox_pages), len(todo_pages))

            sources = []
            for page in inbox_pages[:self.settings.input_limit]:
                self.logger.debug(
                    'kind=script provider=notion Reading Inbox body.',
                    extra={"details": {'page': page['id']}},
                )
                sources.append(self._read_source(client, page, "inbox"))
            for page in todo_pages[:self.settings.input_limit]:
                self.logger.debug(
                    'kind=script provider=notion Reading TODO body.',
                    extra={"details": {'page': page['id']}},
                )
                sources.append(self._read_source(client, page, "todo"))

        self.logger.info("kind=script provider=notion Notion intake read completed: pages=%d.", len(sources))
        return sources

    @trace_call("component", "inputs.read_source")
    def read_source(self, source_url: str) -> SourceMaterial:
        """Read an original source linked from a Workbench proposal.

        Args:
            source_url: Notion URL containing the source page ID.

        Returns:
            Current source material classified by its parent data source.
        """
        source_path = urlsplit(source_url).path
        page_ids = re.findall(
            r"[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
            source_path,
        )
        page_id = page_ids[-1]

        with Client(auth=self.settings.token) as client:
            page = client.pages.retrieve(page_id=page_id)
            parent_id = page["parent"].get("data_source_id", "").replace("-", "")
            inbox_id = self.settings.inbox_data_source_id.replace("-", "")
            todo_id = self.settings.todo_data_source_id.replace("-", "")
            kind: Literal["inbox", "todo"]
            if parent_id == inbox_id:
                kind = "inbox"
            elif parent_id == todo_id:
                kind = "todo"
            else:
                raise ValueError(f"Source page {page_id} does not belong to the configured Inbox or TODO")
            source = self._read_source(client, page, kind)

        return source

    @trace_call("component", "inputs.close_source")
    def close_source(self, source: SourceMaterial) -> None:
        """Mark an input consumed after its proposal has been saved.

        Args:
            source: Inbox or TODO source successfully submitted to Workbench.
        """
        status = "Archived" if source.kind == "inbox" else "handled"
        if source.kind not in {"inbox", "todo"}:
            return
        self.logger.info(
            'kind=script provider=notion Acknowledging source: source=%s target_status=%s.',
            source.kind,
            status,
            extra={"details": {'page': source.page_id}},
        )
        with Client(auth=self.settings.token) as client:
            original = client.pages.retrieve(page_id=source.page_id)
            current = self._read_source(client, original, source.kind)
            if current.text != source.text:
                raise ValueError(f"Source changed before acknowledgement: {source.page_id}")
            client.pages.update(
                page_id=source.page_id,
                properties={"Status": {"select": {"name": status}}},
            )
            verified = client.pages.retrieve(page_id=source.page_id)
            if self._select(verified["properties"], "Status") != status:
                raise ValueError(f"Source acknowledgement failed: {source.page_id}")
        self.logger.info(
            'kind=script provider=notion Source status verified: status=%s.',
            status,
            extra={"details": {'page': source.page_id}},
        )

    def _query_pages(self, client: Client, data_source_id: str, page_filter: dict | None = None, limit: int | None = None) -> list[dict]:
        """Read every page in a data source with an optional property filter.

        Args:
            client: Client owned by the current operation.
            data_source_id: Data source to query.
            page_filter: Notion filter for eligible source pages.
            limit: Optional maximum number of eligible pages to retrieve.

        Returns:
            Page objects from all query result pages.
        """
        pages = []
        cursor = None
        query_number = 0
        self.logger.debug(
            'kind=script provider=notion Querying Notion collection: limit=%s.',
            limit or 'all matching',
            extra={"details": {'data_source': data_source_id}},
        )
        self.logger.debug("kind=script provider=notion Notion collection filter.",
                          extra={"details": {"filter": page_filter}})
        while True:
            arguments = {"data_source_id": data_source_id, "page_size": 100, "result_type": "page"}
            if limit is not None:
                arguments["page_size"] = min(100, limit - len(pages))
                arguments["sorts"] = [{"timestamp": "created_time", "direction": "ascending"}]
            if page_filter is not None:
                arguments["filter"] = page_filter
            if cursor is not None:
                arguments["start_cursor"] = cursor

            response = client.data_sources.query(**arguments)
            query_number += 1
            pages.extend(response["results"])
            self.logger.debug("kind=script provider=notion Notion query batch %d: returned=%d total=%d has_more=%s.",
                             query_number, len(response["results"]), len(pages), response["has_more"])
            if not response["has_more"] or limit is not None and len(pages) >= limit:
                break
            cursor = response["next_cursor"]

        return pages

    def _read_source(self, client: Client, page: dict, kind: Literal["inbox", "todo"]) -> SourceMaterial:
        """Combine source title, task content properties, and page body.

        Args:
            client: Client owned by the current operation.
            page: Notion page including its properties and parent.
            kind: Source role, inbox or todo.

        Returns:
            Source material containing human-authored task content.
        """
        title = self._title(page)
        body = self._markdown(client, page["id"])
        content_parts = [title]
        for name, value in page["properties"].items():
            if name.casefold() in {"content", "description"} and value["type"] == "rich_text":
                content_parts.append(self._plain_text(value["rich_text"]))
        content_parts.append(body)
        text = "\n\n".join(part for part in content_parts if part)

        source = SourceMaterial(
            kind=kind,
            page_id=page["id"],
            url=page["url"],
            title=title,
            text=text,
            revision=page["last_edited_time"],
        )
        return source

    def _title(self, page: dict) -> str:
        """Read a page title independently of the title property's name.

        Args:
            page: Notion page including properties.

        Returns:
            Combined page title.
        """
        title_property = next(value for value in page["properties"].values() if value["type"] == "title")
        title = self._plain_text(title_property["title"])
        return title

    def _select(self, properties: dict, name: str) -> str:
        """Read an optional select value from legacy or current records.

        Args:
            properties: Notion page properties.
            name: Select property name.

        Returns:
            Selected option name, or an empty string when unset.
        """
        option = properties.get(name, {}).get("select")
        name = option["name"] if option else ""
        return name

    def _markdown(self, client: Client, page_id: str) -> str:
        """Read complete Markdown for an input page.

        Args:
            client: Connection owned by the enclosing source operation.
            page_id: Original page identifier.

        Returns:
            Complete source Markdown.
        """
        response = client.pages.retrieve_markdown(page_id=page_id)
        if response["truncated"] or response["unknown_block_ids"]:
            raise ValueError(f"Incomplete input Markdown: {page_id}")
        content = response["markdown"].strip()
        return content

    def _plain_text(self, values: list[dict]) -> str:
        """Join text fragments supplied by the Notion SDK.

        Args:
            values: Rich-text fragments from a title or content property.

        Returns:
            Original human-readable text.
        """
        text = "".join(value.get("plain_text", value.get("text", {}).get("content", "")) for value in values)
        return text
