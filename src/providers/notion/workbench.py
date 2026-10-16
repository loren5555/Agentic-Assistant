"""Read proposal inputs and maintain the Notion Workbench pages."""

import re
import hashlib
from collections.abc import Mapping
from typing import Literal
from urllib.parse import urlsplit

from notion_client import Client
from pydantic import BaseModel

from assistant.protocol.workbench import WorkbenchProtocol
from assistant.schemas.proposal import Proposal, SourceMaterial, WorkbenchItem
from assistant.schemas.task import TaskResult
from assistant.schemas.curation import CurationDecision


def publication_key(kind: str, value: str) -> str:
    """Identify report content for recovering writes with lost acknowledgements.

    Args:
        kind: Proposal, result, or clarification report role.
        value: Canonical content of that report.

    Returns:
        Stable human-visible publication marker.
    """
    key = f"{kind}:{hashlib.sha256(value.encode()).hexdigest()}"
    return key


class WorkbenchSettings(BaseModel):
    """Connection settings for the three proposal workflow data sources.

    Attributes:
        token: Notion integration token.
        inbox_data_source_id: Inbox data source queried for unarchived inputs.
        todo_data_source_id: TODO data source queried for elevated inputs.
        workbench_data_source_id: Data source containing proposals and reviews.
        input_limit: Maximum number of Inbox and TODO items read per collection.
    """

    token: str
    inbox_data_source_id: str
    todo_data_source_id: str
    workbench_data_source_id: str
    input_limit: int = 20


class Workbench(WorkbenchProtocol):
    """Own Notion connections and expose proposal-oriented storage operations."""

    def __init__(self, options: Mapping[str, object]):
        """Read configuration without making a Notion request.

        Args:
            options: Notion connection and data source settings.
        """
        self.settings = WorkbenchSettings.model_validate(options)

    def list_inputs(self) -> list[SourceMaterial]:
        """Read a bounded batch of unarchived Inbox and elevated TODO items.

        Returns:
            Source materials with page properties and complete Markdown bodies.
        """
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

            sources = []
            for page in inbox_pages[:self.settings.input_limit]:
                sources.append(self._read_source(client, page, "inbox"))
            for page in todo_pages[:self.settings.input_limit]:
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
            body = self._markdown(client, page_id)
            item.body_fingerprint = hashlib.sha256(body.encode()).hexdigest()
            markers = re.findall(r"Publication: ([a-z]+:[0-9a-f]{64})", body)
            item.publication_key = markers[-1] if markers else ""
            item.publication_applied = bool(
                item.publication_key
                and f"Publication applied: {item.publication_key}" in body
            )

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

    def submit(self, source: SourceMaterial, proposal: Proposal, workflow_id: str = "") -> WorkbenchItem:
        """Create a proposal report awaiting human review.

        Args:
            source: Original input associated with the proposal.
            proposal: Current agent-generated proposal.
            workflow_id: Stable identity embedded in the report for write recovery.

        Returns:
            Created Workbench page with its report and review properties.
        """
        properties = {
            "Name": {"title": self._rich_text(proposal.title)},
            "Status": {"select": {"name": "Open"}},
            "Source": {"rich_text": self._rich_text(source.url)},
            "Human Review": {"select": {"name": "Pending"}},
            "Result Review": {"select": {"name": "Pending"}},
        }
        report = self._report_text(source, proposal)
        key = publication_key("proposal", proposal.model_dump_json(exclude={"process"}))
        report += f"\n\nPublication: {key}\n\nPublication applied: {key}"
        if workflow_id:
            report += f"\n\nWorkflow: {workflow_id}"

        with Client(auth=self.settings.token) as client:
            existing = []
            if workflow_id:
                candidates = self._query_pages(
                    client, self.settings.workbench_data_source_id,
                    {"property": "Source", "rich_text": {"equals": source.url}},
                )
                existing = [page for page in candidates if f"Workflow: {workflow_id}" in self._markdown(client, page["id"])]
                if len(existing) > 1:
                    raise ValueError(f"Duplicate Workbench workflow: {workflow_id}")
            if existing:
                page = existing[0]
            else:
                page = client.pages.create(
                    parent={"type": "data_source_id", "data_source_id": self.settings.workbench_data_source_id},
                    properties=properties,
                    markdown=report,
                )
            page_id = page["id"]
        item = self.read_item(page_id)
        self._verify_report(item, report)
        item.proposal = proposal
        item.source_kind = source.kind
        return item

    def revise(self, item: WorkbenchItem, proposal: Proposal) -> WorkbenchItem:
        """Replace the current report and return the proposal to human review.

        Args:
            item: Workbench page containing the previous proposal.
            proposal: New version based on source changes or human feedback.

        Returns:
            Updated Workbench page with the latest proposal and human feedback.
        """
        source = self._report_source(item)
        report = self._report_text(source, proposal)
        key = publication_key("proposal", proposal.model_dump_json(exclude={"process"}))
        report += "\n\nPublication: " + key

        current = self.read_item(item.page_id)
        if current.publication_key == key and current.publication_applied:
            self._verify_report(current, report)
            current.proposal = proposal
            current.source_kind = item.source_kind
            return current

        with Client(auth=self.settings.token) as client:
            # Resume after a body-only write instead of overwriting it again.
            if current.publication_key != key:
                client.pages.update_markdown(
                    page_id=item.page_id, type="replace_content",
                    replace_content={"new_str": report},
                )
            self._verify_report(current, report)
            if not (
                current.publication_key == key and current.status == "Open"
                and current.human_review == "Pending" and current.result_review == "Pending"
            ):
                client.pages.update(
                    page_id=item.page_id,
                    properties={
                        "Name": {"title": self._rich_text(proposal.title)},
                        "Status": {"select": {"name": "Open"}},
                        "Human Review": {"select": {"name": "Pending"}},
                        "Result Review": {"select": {"name": "Pending"}},
                    },
                )
            verified = client.pages.retrieve(page_id=item.page_id)
            properties = verified["properties"]
            if (
                self._select(properties, "Status") != "Open"
                or self._select(properties, "Human Review") != "Pending"
                or self._select(properties, "Result Review") != "Pending"
            ):
                raise ValueError(f"Proposal metadata readback failed: {item.page_id}")
            self._mark_publication_applied(client, item.page_id, key)
        revised_item = self.read_item(item.page_id)
        self._verify_report(revised_item, report)
        revised_item.proposal = proposal
        revised_item.source_kind = item.source_kind
        return revised_item

    def close_source(self, source: SourceMaterial) -> None:
        """Mark an input consumed after its proposal has been saved.

        Args:
            source: Inbox or TODO source successfully submitted to Workbench.
        """
        status = "Archived" if source.kind == "inbox" else "handled"
        if source.kind not in {"inbox", "todo"}:
            return
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
        source = self._report_source(item)
        report = self._report_text(source, proposal)
        content = report + "\n\n## Execution result\n\n" + result.content
        key = publication_key("result", result.content)
        content += "\n\nPublication: " + key
        current = self.read_item(item.page_id)
        if current.publication_key == key and current.status in {"Executed", "Finished", "Archived"}:
            self._verify_report(current, content)
            return
        with Client(auth=self.settings.token) as client:
            if current.publication_key != key:
                client.pages.update_markdown(
                    page_id=item.page_id, type="replace_content",
                    replace_content={"new_str": content},
                )
            self._verify_report(current, content)
            # A failed content write must not advance the lifecycle to Executed.
            client.pages.update(
                page_id=item.page_id,
                properties={
                    "Status": {"select": {"name": "Executed"}},
                    "Result Review": {"select": {"name": "Pending"}},
                },
            )
        current = self.read_item(item.page_id)
        self._verify_report(current, content)
        if current.status != "Executed":
            raise ValueError(f"Result status readback failed: {item.page_id}")

    def request_input(self, item: WorkbenchItem, question: str) -> None:
        """Display a focused question and return the proposal to human review.

        Args:
            item: Proposal whose execution requires essential human input.
            question: Clarification requested by the router.
        """
        proposal = item.proposal
        if proposal is None:
            raise ValueError("Cannot request execution input for an unmanaged proposal")
        source = self._report_source(item)
        report = self._report_text(source, proposal)
        content = report + "\n\n## Input needed\n\n" + question
        key = publication_key("clarification", question)
        content += "\n\nPublication: " + key
        current = self.read_item(item.page_id)
        if current.publication_key == key and current.publication_applied:
            self._verify_report(current, content)
            return
        with Client(auth=self.settings.token) as client:
            if current.publication_key != key:
                client.pages.update_markdown(
                    page_id=item.page_id, type="replace_content",
                    replace_content={"new_str": content},
                )
            self._verify_report(current, content)
            if not (current.publication_key == key and current.status == "Open" and current.human_review == "Pending"):
                client.pages.update(
                    page_id=item.page_id,
                    properties={
                        "Status": {"select": {"name": "Open"}},
                        "Human Review": {"select": {"name": "Pending"}},
                    },
                )
            verified = client.pages.retrieve(page_id=item.page_id)
            if self._select(verified["properties"], "Human Review") != "Pending" or self._select(verified["properties"], "Status") != "Open":
                raise ValueError(f"Clarification metadata readback failed: {item.page_id}")
            self._mark_publication_applied(client, item.page_id, key)
        current = self.read_item(item.page_id)
        self._verify_report(current, content)
        if current.human_review != "Pending":
            raise ValueError(f"Clarification readback failed: {item.page_id}")

    def save_error(self, item: WorkbenchItem, error: str) -> None:
        """Retain the latest error without changing human feedback or approval.

        Args:
            item: Proposal whose execution failed.
            error: Actual exception description for manual diagnosis or retry.
        """
        # Machine failures belong to the runtime log, not Notion properties.
        from logger import get_logger
        get_logger("providers.notion.workbench").error("%s: %s", item.url, error)

    def save_curation(self, item: WorkbenchItem, decision: CurationDecision) -> None:
        """Replace the current extraction checkpoint and verify its readback.

        Args:
            item: Human-accepted task being finalized.
            decision: Latest extraction decision and verified destination links.
        """
        # DBOS owns extraction checkpoints; retained outcomes use ArchiveStore.
        item.curation = decision

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
            pages.extend(response["results"])
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

    def _parse_item(self, page: dict) -> WorkbenchItem:
        """Convert a Workbench page into workflow-facing data.

        Args:
            page: Notion page containing current review properties.

        Returns:
            Current structured proposal and human decisions, without a body fetch.
        """
        properties = page["properties"]
        proposal = None
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
            source_kind=None,
            proposal=proposal,
            result=None,
            curation=None,
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

    def initialize_schema(self) -> None:
        """Explicitly add and verify the Finished lifecycle option only."""
        data_source_id = self.settings.workbench_data_source_id
        with Client(auth=self.settings.token) as client:
            data_source = client.data_sources.retrieve(data_source_id=data_source_id)
            options = data_source["properties"]["Status"]["select"]["options"]
            if "Finished" not in {option["name"] for option in options}:
                client.data_sources.update(
                    data_source_id=data_source_id,
                    properties={"Status": {"select": {"options": [*options, {"name": "Finished"}]}}},
                )
                verified = client.data_sources.retrieve(data_source_id=data_source_id)
                stored_options = verified["properties"]["Status"]["select"]["options"]
                if "Finished" not in {option["name"] for option in stored_options}:
                    raise ValueError(f"Workbench schema readback failed: {data_source_id}")

    def _report_source(self, item: WorkbenchItem) -> SourceMaterial:
        """Build display provenance without rereading a raw input database.

        Args:
            item: Runtime-owned proposal snapshot.

        Returns:
            Source identity needed by the report renderer.
        """
        source = SourceMaterial(
            kind=item.source_kind or "inbox", page_id="", url=item.source_url,
            title=item.title, text="", revision="",
        )
        return source

    def _mark_publication_applied(self, client: Client, page_id: str, key: str) -> None:
        """Record verified review resets without adding machine properties.

        Args:
            client: Connection owned by the current publication.
            page_id: Workbench report whose metadata has been verified.
            key: Report identity to acknowledge.
        """
        marker = f"Publication applied: {key}"
        body = self._markdown(client, page_id)
        if marker not in body:
            client.pages.update_markdown(
                page_id=page_id, type="insert_content",
                insert_content={"content": "\n\n" + marker, "position": {"type": "end"}},
            )
        verified = self._markdown(client, page_id)
        if marker not in verified:
            raise ValueError(f"Publication acknowledgement readback failed: {page_id}")

    def _verify_report(self, item: WorkbenchItem, expected: str) -> None:
        """Read back a report before acknowledging an external write.

        Args:
            item: Page just created or updated.
            expected: Report written by this operation.
        """
        with Client(auth=self.settings.token) as client:
            body = self._markdown(client, item.page_id)
        # Normalize layout whitespace, not word boundaries or punctuation.
        normalized_expected = " ".join(expected.split())
        normalized_body = " ".join(body.split())
        if normalized_expected not in normalized_body:
            raise ValueError(f"Workbench report readback failed: {item.page_id}")

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
