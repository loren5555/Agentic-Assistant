"""Read proposal inputs and maintain the Notion Workbench pages."""

import re
from collections.abc import Mapping
from typing import Literal
from urllib.parse import urlsplit

from notion_client import Client
from pydantic import BaseModel

from assistant.protocol.workbench import WorkbenchProtocol
from assistant.schemas.proposal import Proposal, SourceMaterial, WorkbenchItem
from assistant.schemas.task import TaskResult
from assistant.schemas.curation import CurationDecision


class WorkbenchSettings(BaseModel):
    """Connection settings for the three proposal workflow data sources.

    Attributes:
        token: Notion integration token.
        inbox_data_source_id: Inbox data source queried for unarchived inputs.
        todo_data_source_id: TODO data source queried for elevated inputs.
        workbench_data_source_id: Data source containing proposals and reviews.
    """

    token: str
    inbox_data_source_id: str
    todo_data_source_id: str
    workbench_data_source_id: str


class Workbench(WorkbenchProtocol):
    """Own Notion connections and expose proposal-oriented storage operations."""

    def __init__(self, options: Mapping[str, object]):
        """Read configuration without making a Notion request.

        Args:
            options: Notion connection and data source settings.
        """
        self.settings = WorkbenchSettings.model_validate(options)

    def list_inputs(self) -> list[SourceMaterial]:
        """Read all unarchived Inbox and elevated TODO items.

        Returns:
            Source materials with page properties and complete Markdown bodies.
        """
        with Client(auth=self.settings.token) as client:
            inbox_pages = self._query_pages(
                client,
                self.settings.inbox_data_source_id,
                {"property": "Status", "select": {"does_not_equal": "Archived"}},
            )
            todo_pages = self._query_pages(
                client,
                self.settings.todo_data_source_id,
                {"property": "Status", "select": {"equals": "elevated"}},
            )

            sources = []
            for page in inbox_pages:
                sources.append(self._read_source(client, page, "inbox"))
            for page in todo_pages:
                sources.append(self._read_source(client, page, "todo"))

        return sources

    def list_items(self, statuses: list[str]) -> list[WorkbenchItem]:
        """Read current proposals and reviews directly from page properties.

        Args:
            statuses: Lifecycle states included in the Notion query.

        Returns:
            Matching pages and their proposal and review content.
        """
        page_filter = {
            "or": [
                {"property": "Status", "select": {"equals": status}}
                for status in statuses
            ],
        }

        with Client(auth=self.settings.token) as client:
            pages = self._query_pages(
                client, self.settings.workbench_data_source_id, page_filter,
            )
            items = [self._parse_item(page) for page in pages]

        return items

    def read_item(self, page_id: str) -> WorkbenchItem:
        """Read a proposal immediately before acting on its review.

        Args:
            page_id: Workbench page ID.

        Returns:
            Current proposal page and human review values.
        """
        with Client(auth=self.settings.token) as client:
            page = client.pages.retrieve(page_id=page_id)
            item = self._parse_item(page)

        return item

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

    def submit(self, source: SourceMaterial, proposal: Proposal) -> WorkbenchItem:
        """Create a proposal report awaiting human review.

        Args:
            source: Original input associated with the proposal.
            proposal: Current agent-generated proposal.

        Returns:
            Created Workbench page with its report and review properties.
        """
        properties = {
            "Name": {"title": self._rich_text(proposal.title)},
            "Status": {"select": {"name": "Open"}},
            "Source": {"rich_text": self._rich_text(source.url)},
            "Human Review": {"select": {"name": "Pending"}},
            "Result Review": {"select": {"name": "Pending"}},
            **self._proposal_properties(source, proposal),
        }
        report = self._report_text(source, proposal)

        with Client(auth=self.settings.token) as client:
            page = client.pages.create(
                parent={"type": "data_source_id", "data_source_id": self.settings.workbench_data_source_id},
                properties=properties,
                markdown=report,
            )
            item = self._parse_item(page)

        return item

    def revise(self, item: WorkbenchItem, proposal: Proposal) -> WorkbenchItem:
        """Replace the current report and return the proposal to human review.

        Args:
            item: Workbench page containing the previous proposal.
            proposal: New version based on source changes or human feedback.

        Returns:
            Updated Workbench page with the latest proposal and human feedback.
        """
        source = self.read_source(item.source_url)
        report = self._report_text(source, proposal)

        with Client(auth=self.settings.token) as client:
            # Replace the display first; publish new approval metadata afterward.
            client.pages.update_markdown(
                page_id=item.page_id,
                type="replace_content",
                replace_content={"new_str": report},
            )
            page = client.pages.update(
                page_id=item.page_id,
                properties={
                    "Name": {"title": self._rich_text(proposal.title)},
                    "Status": {"select": {"name": "Open"}},
                    "Human Review": {"select": {"name": "Pending"}},
                    "Result Review": {"select": {"name": "Pending"}},
                    "Result Data": {"rich_text": []},
                    "Execution Error": {"rich_text": []},
                    "Curation Data": {"rich_text": []},
                    **self._proposal_properties(source, proposal),
                },
            )
            revised_item = self._parse_item(page)

        return revised_item

    def close_source(self, source: SourceMaterial) -> None:
        """Mark an input consumed after its proposal has been saved.

        Args:
            source: Inbox or TODO source successfully submitted to Workbench.
        """
        status = "Archived" if source.kind == "inbox" else "handled"
        with Client(auth=self.settings.token) as client:
            client.pages.update(
                page_id=source.page_id,
                properties={"Status": {"select": {"name": status}}},
            )

    def set_status(self, item: WorkbenchItem, status: str) -> None:
        """Update a proposal lifecycle status while retaining human feedback.

        Args:
            item: Workbench page to update.
            status: Lifecycle value such as Deprecated or Archived.
        """
        with Client(auth=self.settings.token) as client:
            client.pages.update(
                page_id=item.page_id,
                properties={"Status": {"select": {"name": status}}},
            )
            page = client.pages.retrieve(page_id=item.page_id)
            if self._select(page["properties"], "Status") != status:
                raise ValueError(f"Workbench status readback failed: {item.page_id}")

    def save_result(self, item: WorkbenchItem, result: TaskResult) -> None:
        """Replace the displayed deliverable and mark successful work Executed.

        Args:
            item: Proposal snapshot defining the executed scope.
            result: Completed output, excluding telemetry from Notion storage.
        """
        proposal = item.proposal
        if proposal is None:
            raise ValueError("Cannot save execution results for an unmanaged proposal")
        source = self.read_source(item.source_url)
        report = self._report_text(source, proposal)
        content = report + "\n\n## Execution result\n\n" + result.content
        data = result.model_dump_json(exclude={"process"})
        with Client(auth=self.settings.token) as client:
            client.pages.update_markdown(
                page_id=item.page_id,
                type="replace_content",
                replace_content={"new_str": content},
            )
            # A failed content write must not advance the lifecycle to Executed.
            client.pages.update(
                page_id=item.page_id,
                properties={
                    "Result Data": {"rich_text": self._rich_text(data)},
                    "Execution Error": {"rich_text": []},
                    "Status": {"select": {"name": "Executed"}},
                    "Result Review": {"select": {"name": "Pending"}},
                    "Curation Data": {"rich_text": []},
                },
            )

    def request_input(self, item: WorkbenchItem, question: str) -> None:
        """Display a focused question and return the proposal to human review.

        Args:
            item: Proposal whose execution requires essential human input.
            question: Clarification requested by the router.
        """
        proposal = item.proposal
        if proposal is None:
            raise ValueError("Cannot request execution input for an unmanaged proposal")
        source = self.read_source(item.source_url)
        report = self._report_text(source, proposal)
        content = report + "\n\n## Input needed\n\n" + question
        with Client(auth=self.settings.token) as client:
            client.pages.update_markdown(
                page_id=item.page_id,
                type="replace_content",
                replace_content={"new_str": content},
            )
            client.pages.update(
                page_id=item.page_id,
                properties={
                    "Status": {"select": {"name": "Open"}},
                    "Human Review": {"select": {"name": "Pending"}},
                },
            )

    def save_error(self, item: WorkbenchItem, error: str) -> None:
        """Retain the latest error without changing human feedback or approval.

        Args:
            item: Proposal whose execution failed.
            error: Actual exception description for manual diagnosis or retry.
        """
        with Client(auth=self.settings.token) as client:
            client.pages.update(
                page_id=item.page_id,
                properties={"Execution Error": {"rich_text": self._rich_text(error)}},
            )

    def save_curation(self, item: WorkbenchItem, decision: CurationDecision) -> None:
        """Replace the current extraction checkpoint and verify its readback.

        Args:
            item: Human-accepted task being finalized.
            decision: Latest extraction decision and verified destination links.
        """
        data = decision.model_dump_json()
        with Client(auth=self.settings.token) as client:
            client.pages.update(
                page_id=item.page_id,
                properties={
                    "Curation Data": {"rich_text": self._rich_text(data)},
                    "Execution Error": {"rich_text": []},
                },
            )
            page = client.pages.retrieve(page_id=item.page_id)
            stored_data = self._plain_text(page["properties"]["Curation Data"]["rich_text"])
            verified = CurationDecision.model_validate_json(stored_data)
            if verified != decision:
                raise ValueError(f"Curation checkpoint readback failed: {item.page_id}")

    def _query_pages(self, client: Client, data_source_id: str, page_filter: dict | None = None) -> list[dict]:
        """Read every page in a data source with an optional property filter.

        Args:
            client: Client owned by the current operation.
            data_source_id: Data source to query.
            page_filter: Notion filter for eligible source pages.

        Returns:
            Page objects from all query result pages.
        """
        pages = []
        cursor = None
        while True:
            arguments = {"data_source_id": data_source_id, "page_size": 100, "result_type": "page"}
            if page_filter is not None:
                arguments["filter"] = page_filter
            if cursor is not None:
                arguments["start_cursor"] = cursor

            response = client.data_sources.query(**arguments)
            pages.extend(response["results"])
            if not response["has_more"]:
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

    def _parse_item(self, page: dict) -> WorkbenchItem:
        """Convert a Workbench page into workflow-facing data.

        Args:
            page: Notion page containing current review properties.

        Returns:
            Current structured proposal and human decisions, without a body fetch.
        """
        properties = page["properties"]
        data = self._plain_text(properties.get("Proposal Data", {}).get("rich_text", []))
        proposal = None
        if data:
            proposal = Proposal.model_validate_json(data)
            proposal.version = int(properties["Proposal Version"]["number"])

        source_kind = self._plain_text(properties.get("Source Kind", {}).get("rich_text", []))
        result_data = self._plain_text(properties.get("Result Data", {}).get("rich_text", []))
        result = TaskResult.model_validate_json(result_data) if result_data else None
        curation_data = self._plain_text(properties.get("Curation Data", {}).get("rich_text", []))
        curation = CurationDecision.model_validate_json(curation_data) if curation_data else None
        item = WorkbenchItem(
            page_id=page["id"],
            url=page["url"],
            title=self._title(page),
            status=self._select(properties, "Status"),
            human_review=self._select(properties, "Human Review"),
            human_instruction=self._plain_text(properties.get("Human Instruction", {}).get("rich_text", [])),
            result_review=self._select(properties, "Result Review"),
            result_feedback=self._plain_text(properties.get("Result Feedback", {}).get("rich_text", [])),
            source_url=self._source_url(properties),
            source_kind=source_kind or None,
            proposal=proposal,
            result=result,
            curation=curation,
        )
        return item

    def _markdown(self, client: Client, page_id: str) -> str:
        """Read a complete page body rather than a truncated source snapshot.

        Args:
            client: Client owned by the current operation.
            page_id: Notion page to read.

        Returns:
            Markdown body of the page.
        """
        content = client.pages.retrieve_markdown(page_id=page_id)
        if content["truncated"] or content["unknown_block_ids"]:
            raise ValueError(f"Notion page {page_id} has incomplete Markdown content")
        body = content["markdown"].strip()
        return body

    def _report_text(self, source: SourceMaterial, proposal: Proposal) -> str:
        """Render only the current human-readable proposal as Markdown.

        Args:
            source: Original source used for this proposal version.
            proposal: Current proposal to display.

        Returns:
            Report without machine metadata, model traces, or prior versions.
        """
        lines = [
            f"## {proposal.title}",
            f"Source ({source.kind}): {source.url}",
            f"Understanding: {proposal.understanding}",
            f"Purpose: {proposal.purpose}",
            f"Reason: {proposal.reason}",
            f"Action: {proposal.action}",
            "Plan:",
            *[f"{index}. {step}" for index, step in enumerate(proposal.plan, start=1)],
            f"Expected result: {proposal.expected_result}",
        ]
        report = "\n\n".join(lines)
        return report

    def _proposal_properties(self, source: SourceMaterial, proposal: Proposal) -> dict:
        """Store the latest proposal separately from its display report.

        Args:
            source: Original input whose role is retained for lifecycle updates.
            proposal: Current proposal, including its content fingerprint.

        Returns:
            Notion properties containing current data only, without process history.
        """
        data = proposal.model_dump_json(exclude={"process", "version"})
        properties = {
            "Proposal Version": {"number": proposal.version},
            "Proposal Data": {"rich_text": self._rich_text(data)},
            "Source Kind": {"rich_text": self._rich_text(source.kind)},
        }
        return properties

    def initialize_schema(self) -> None:
        """Explicitly initialize workflow data properties and final status options."""
        data_source_id = self.settings.workbench_data_source_id
        definitions = {
            "Proposal Version": {"number": {"format": "number"}},
            "Proposal Data": {"rich_text": {}},
            "Source Kind": {"rich_text": {}},
            "Result Data": {"rich_text": {}},
            "Execution Error": {"rich_text": {}},
            "Curation Data": {"rich_text": {}},
        }
        with Client(auth=self.settings.token) as client:
            data_source = client.data_sources.retrieve(data_source_id=data_source_id)
            missing = {
                name: definition for name, definition in definitions.items()
                if name not in data_source["properties"]
            }
            options = data_source["properties"]["Status"]["select"]["options"]
            if "Finished" not in {option["name"] for option in options}:
                missing["Status"] = {"select": {"options": [*options, {"name": "Finished"}]}}
            if missing:
                client.data_sources.update(data_source_id=data_source_id, properties=missing)

    def _rich_text(self, text: str) -> list[dict]:
        """Split text into the SDK's rich-text fragments.

        Args:
            text: Text to write without changing its content.

        Returns:
            Text fragments each within Notion's content length limit.
        """
        fragments = [
            {"type": "text", "text": {"content": text[offset:offset + 2000]}}
            for offset in range(0, len(text), 2000)
        ]
        return fragments

    def _plain_text(self, fragments: list[dict]) -> str:
        """Join text fragments returned by Notion.

        Args:
            fragments: Rich-text values read from a page property.

        Returns:
            Combined plain text.
        """
        text = "".join(fragment["plain_text"] for fragment in fragments)
        return text

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

    def _source_url(self, properties: dict) -> str:
        """Read the first original source link without dropping legacy mentions.

        Args:
            properties: Notion page properties including Source rich text.

        Returns:
            Source URL found in text, hyperlinks, or page mentions.
        """
        source_property = properties.get("Source", {})
        if source_property.get("url"):
            return source_property["url"]

        for fragment in source_property.get("rich_text", []):
            if fragment.get("href"):
                return fragment["href"]
            mention = fragment.get("mention", {})
            if mention.get("type") == "page":
                page_id = mention["page"]["id"].replace("-", "")
                return f"https://www.notion.so/{page_id}"
            match = re.search(r"https?://[^\s<>]+", fragment.get("plain_text", ""))
            if match:
                return match.group(0)

        return ""
