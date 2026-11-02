"""Maintain proposal reports, human reviews, and results in Notion Workbench."""

from collections.abc import Mapping
import hashlib
import re

from notion_client import Client

from assistant.components.curator.models import CurationDecision
from assistant.components.inputs.models import SourceMaterial
from assistant.components.proposer.models import Proposal
from assistant.components.task_worker.models import TaskResult
from assistant.components.workbench.models import WorkbenchItem, result_publication_key
from assistant.components.workbench.protocol import WorkbenchProtocol
from logger import get_logger, trace_call
from plugins._shared.notion.config import NotionSettings
from plugins._shared.notion.schema import ensure_number, ensure_rich_text, ensure_select_option


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


class Workbench(WorkbenchProtocol):
    """Own Notion connections and expose proposal-oriented storage operations."""

    def __init__(self, options: Mapping[str, object]):
        """Read configuration without making a Notion request.

        Args:
            options: Notion connection and data source settings.
        """
        self.settings = NotionSettings.model_validate(options)
        self.logger = get_logger("plugins.workbench.notion")

    @trace_call("component", "workbench.list_items")
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
        self.logger.info("kind=script provider=notion Workbench status query completed: statuses=%s pages=%d.", statuses, len(items))
        return items

    @trace_call("component", "workbench.read_item")
    def read_item(self, page_id: str) -> WorkbenchItem:
        """Read a proposal immediately before acting on its review.

        Args:
            page_id: Workbench page ID.

        Returns:
            Current proposal page and human review values.
        """
        self.logger.debug(
            'kind=script provider=notion Reading Workbench properties.',
            extra={"details": {'page': page_id}},
        )
        with Client(auth=self.settings.token) as client:
            page = client.pages.retrieve(page_id=page_id)
            item = self._parse_item(page)
        self.logger.debug(
            'kind=script provider=notion Workbench properties read: status=%s confirmed=%s.',
            item.status,
            item.publication_applied,
            extra={"details": {'page': page_id}},
        )
        return item

    @trace_call("component", "workbench.submit")
    def submit(self, source: SourceMaterial, proposal: Proposal, workflow_id: str = "") -> WorkbenchItem:
        """Create a proposal report awaiting human review.

        Args:
            source: Original input associated with the proposal.
            proposal: Current agent-generated proposal.
            workflow_id: Stable identity embedded in the report for write recovery.

        Returns:
            Created Workbench page with its report and review properties.
        """
        self.logger.info(
            'kind=script provider=notion Submitting Workbench proposal: title=%r source=%s version=%d.',
            proposal.title,
            source.kind,
            proposal.version,
            extra={"details": {'page': source.page_id, 'workflow': workflow_id}},
        )
        properties = {
            "Name": {"title": self._rich_text(proposal.title)},
            "Status": {"select": {"name": "Open"}},
            "Source": {"rich_text": self._rich_text(source.url)},
            "Source Kind": {"rich_text": self._rich_text(source.kind)},
            "Execution Error": {"rich_text": []},
            "Human Review": {"select": {"name": "Pending"}},
            "Result Review": {"select": {"name": "Pending"}},
            "Proposal Version": {"number": proposal.version},
        }
        report = self._report_text(source, proposal)
        key = publication_key("proposal", proposal.model_dump_json(exclude={"process"}))
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
                self.logger.info(
                    'kind=script provider=notion Recovering existing Workbench proposal; checking confirmation.',
                    extra={"details": {'page': page['id']}},
                )
            else:
                self.logger.info(
                    'kind=script provider=notion Creating Workbench proposal: title=%r.',
                    proposal.title,
                    extra={"details": {'source_page': source.page_id}},
                )
                page = client.pages.create(
                    parent={"type": "data_source_id", "data_source_id": self.settings.workbench_data_source_id},
                    properties=properties,
                    markdown=report,
                )
            page_id = page["id"]
            stored_key = self._plain_text(page["properties"].get("Publication Key", {}).get("rich_text", []))
            if stored_key != key:
                # A previous attempt may have created the page but failed before
                # confirming it. Reuse that page rather than creating another.
                if existing:
                    client.pages.update_markdown(
                        page_id=page_id, type="replace_content",
                        replace_content={"new_str": report},
                    )
                self._confirm_publication(client, page_id, key, {
                    "Proposal Version": {"number": proposal.version},
                    "Source Kind": {"rich_text": self._rich_text(source.kind)},
                    "Execution Error": {"rich_text": []},
                })
            else:
                self.logger.info(
                    'kind=checkpoint Workbench proposal already confirmed; preserving human review.',
                    extra={"details": {'page': page_id}},
                )
        item = self.read_item(page_id)
        item.proposal = proposal
        item.source_kind = source.kind
        self.logger.info(
            'kind=script provider=notion Workbench proposal verified: title=%r status=%s.',
            item.title,
            item.status,
            extra={"details": {'page': item.page_id, 'url': item.url}},
        )
        return item

    @trace_call("component", "workbench.revise")
    def revise(self, item: WorkbenchItem, proposal: Proposal) -> WorkbenchItem:
        """Publish a revision, then confirm its review reset through properties.

        Args:
            item: Page containing the previous proposal.
            proposal: Revised proposal based on source material and feedback.

        Returns:
            Confirmed proposal with current human review values.
        """
        self.logger.info(
            'kind=script provider=notion Revising Workbench proposal: title=%r version=%d.',
            proposal.title,
            proposal.version,
            extra={"details": {'page': item.page_id}},
        )
        key = publication_key("proposal", proposal.model_dump_json(exclude={"process"}))
        current = self.read_item(item.page_id)
        if current.publication_key == key:
            current.proposal = proposal
            current.source_kind = item.source_kind
            self.logger.info(
                'kind=checkpoint Proposal revision already confirmed; human review preserved.',
                extra={"details": {'page': item.page_id}},
            )
            return current

        source = self._report_source(item)
        report = self._report_text(source, proposal)
        with Client(auth=self.settings.token) as client:
            client.pages.update_markdown(
                page_id=item.page_id, type="replace_content",
                replace_content={"new_str": report},
            )
            self._confirm_publication(client, item.page_id, key, {
                "Name": {"title": self._rich_text(proposal.title)},
                "Proposal Version": {"number": proposal.version},
                "Source Kind": {"rich_text": self._rich_text(source.kind)},
                "Execution Error": {"rich_text": []},
                "Status": {"select": {"name": "Open"}},
                "Human Review": {"select": {"name": "Pending"}},
                "Result Review": {"select": {"name": "Pending"}},
            })
        revised = self.read_item(item.page_id)
        revised.proposal = proposal
        revised.source_kind = item.source_kind
        self.logger.info(
            'kind=script provider=notion Proposal revision confirmed: title=%r version=%d approval=%s.',
            revised.title,
            proposal.version,
            revised.human_review,
            extra={"details": {'page': item.page_id}},
        )
        return revised

    @trace_call("component", "workbench.set_status")
    def set_status(self, item: WorkbenchItem, status: str) -> None:
        """Update a proposal lifecycle status while retaining human feedback.

        Args:
            item: Workbench page to update.
            status: Lifecycle value such as Deprecated or Archived.
        """
        self.logger.info(
            'kind=script provider=notion Updating Workbench status: title=%r from=%s to=%s.',
            item.title,
            item.status,
            status,
            extra={"details": {'page': item.page_id}},
        )
        with Client(auth=self.settings.token) as client:
            client.pages.update(
                page_id=item.page_id,
                properties={"Status": {"select": {"name": status}}},
            )
            page = client.pages.retrieve(page_id=item.page_id)
            if self._select(page["properties"], "Status") != status:
                raise ValueError(f"Workbench status readback failed: {item.page_id}")
        self.logger.info(
            'kind=script provider=notion Workbench status verified: title=%r status=%s.',
            item.title,
            status,
            extra={"details": {'page': item.page_id}},
        )

    @trace_call("component", "workbench.save_result")
    def save_result(self, item: WorkbenchItem, result: TaskResult) -> None:
        """Write the deliverable before confirming its Executed state.

        Args:
            item: Proposal snapshot defining the approved scope.
            result: Completed deliverable, excluding execution telemetry.
        """
        self.logger.info(
            'kind=script provider=notion Saving execution result: title=%r characters=%d action=%s.',
            item.title,
            len(result.content),
            result.action_id,
            extra={"details": {'page': item.page_id}},
        )
        if item.proposal is None:
            raise ValueError("Cannot save execution results for an unmanaged proposal")
        key = result_publication_key(item.proposal.version, result.content)
        current = self.read_item(item.page_id)
        if current.publication_key == key:
            if current.status == "Open" or (current.status == "Executed" and current.result_review == "Unqualified" and item.result_review == "Unqualified"):
                with Client(auth=self.settings.token) as client:
                    self._confirm_publication(client, item.page_id, key, {
                        "Status": {"select": {"name": "Executed"}},
                        "Result Review": {"select": {"name": "Pending"}},
                        "Execution Error": {"rich_text": []},
                    })
                self.logger.info('Existing result advanced to Executed: title=%r.', item.title)
                return
            if current.execution_error:
                self.save_error(current, "")
            self.logger.info(
                'kind=checkpoint Execution result already confirmed: status=%s; human acceptance preserved.',
                current.status,
                extra={"details": {'page': item.page_id}},
            )
            return

        source = self._report_source(item)
        report = self._report_text(source, item.proposal)
        content = report + "\n\n## Execution result\n\n" + result.content
        with Client(auth=self.settings.token) as client:
            client.pages.update_markdown(
                page_id=item.page_id, type="replace_content",
                replace_content={"new_str": content},
            )
            # The code and lifecycle state are one property update, after the
            # body call succeeds. A retry must not reset subsequent human review.
            self._confirm_publication(client, item.page_id, key, {
                "Status": {"select": {"name": "Executed"}},
                "Result Review": {"select": {"name": "Pending"}},
                "Execution Error": {"rich_text": []},
            })
        self.logger.info(
            'kind=script provider=notion Execution result confirmed: title=%r status=Executed acceptance=Pending.',
            item.title,
            extra={"details": {'page': item.page_id}},
        )

    @trace_call("component", "workbench.request_input")
    def request_input(self, item: WorkbenchItem, question: str) -> None:
        """Publish a question, then confirm its return to human review.

        Args:
            item: Managed proposal requiring additional user input.
            question: Focused clarification requested by the router.
        """
        self.logger.info(
            'kind=script provider=notion Publishing clarification: question_characters=%d.',
            len(question),
            extra={"details": {'page': item.page_id}},
        )
        if item.proposal is None:
            raise ValueError("Cannot request execution input for an unmanaged proposal")
        key = publication_key("clarification", question)
        current = self.read_item(item.page_id)
        if current.publication_key == key:
            self.logger.info(
                'kind=checkpoint Clarification already confirmed; human review preserved.',
                extra={"details": {'page': item.page_id}},
            )
            return

        source = self._report_source(item)
        report = self._report_text(source, item.proposal)
        content = report + "\n\n## Input needed\n\n" + question
        with Client(auth=self.settings.token) as client:
            client.pages.update_markdown(
                page_id=item.page_id, type="replace_content",
                replace_content={"new_str": content},
            )
            self._confirm_publication(client, item.page_id, key, {
                "Status": {"select": {"name": "Open"}},
                "Human Review": {"select": {"name": "Pending"}},
                "Execution Error": {"rich_text": []},
            })
        self.logger.info(
            'kind=script provider=notion Clarification confirmed: status=Open approval=Pending.',
            extra={"details": {'page': item.page_id}},
        )

    @trace_call("component", "workbench.save_error")
    def save_error(self, item: WorkbenchItem, error: str) -> None:
        """Retain the latest error without changing human feedback or approval.

        Args:
            item: Proposal whose execution failed.
            error: Actual exception description for manual diagnosis or retry.
        """
        self.logger.info("kind=script provider=notion Publishing execution error.",
                         extra={"details": {"page": item.page_id}})
        # Keep a short human-facing diagnosis; DBOS and logs retain full details.
        summary = error[:4000]
        with Client(auth=self.settings.token) as client:
            client.pages.update(page_id=item.page_id, properties={
                "Execution Error": {"rich_text": self._rich_text(summary)},
            })
            page = client.pages.retrieve(page_id=item.page_id)
            stored = self._plain_text(page["properties"]["Execution Error"]["rich_text"])
            if stored != summary:
                raise ValueError(f"Execution error readback failed: {item.page_id}")
        self.logger.info("kind=script provider=notion Execution error published; review state unchanged.",
                         extra={"details": {"page": item.page_id}})

    @trace_call("component", "workbench.save_curation")
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
            source_kind=self._plain_text(properties.get("Source Kind", {}).get("rich_text", [])) or None,
            proposal=proposal,
            result=None,
            curation=None,
            publication_key=self._plain_text(properties.get("Publication Key", {}).get("rich_text", [])),
            publication_applied=bool(properties.get("Publication Key", {}).get("rich_text", [])),
            proposal_version=properties.get("Proposal Version", {}).get("number"),
            execution_error=self._plain_text(properties.get("Execution Error", {}).get("rich_text", [])),
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

    @trace_call("component", "workbench.initialize_schema")
    def initialize_schema(self) -> None:
        """Initialize lifecycle, visible proposal version, and publication receipt."""
        with Client(auth=self.settings.token) as client:
            ensure_select_option(client, self.settings.workbench_data_source_id, "Status", "Finished")
            ensure_rich_text(client, self.settings.workbench_data_source_id, "Publication Key")
            ensure_number(client, self.settings.workbench_data_source_id, "Proposal Version")
            ensure_rich_text(client, self.settings.workbench_data_source_id, "Source Kind")
            ensure_rich_text(client, self.settings.workbench_data_source_id, "Execution Error")

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

    def _confirm_publication(
        self, client: Client, page_id: str, key: str, properties: dict | None = None,
    ) -> None:
        """Write a publication receipt after body success and read back only it.

        Args:
            client: Connection owned by the publication operation.
            page_id: Workbench page whose body write succeeded.
            key: Deterministic receipt for this report.
            properties: Lifecycle fields applied together with the receipt.
        """
        self.logger.info(
            'kind=script provider=notion Confirming Workbench publication.',
            extra={"details": {'page': page_id}},
        )
        updates = dict(properties or {})
        updates["Publication Key"] = {"rich_text": self._rich_text(key)}
        try:
            client.pages.update(page_id=page_id, properties=updates)
            page = client.pages.retrieve(page_id=page_id)
            stored = self._plain_text(page["properties"]["Publication Key"]["rich_text"])
            if stored != key:
                raise ValueError(f"Workbench publication key readback failed: {page_id}")
        except Exception:
            self.logger.exception(
                'kind=script provider=notion Workbench publication confirmation failed.',
                extra={"details": {'page': page_id}},
            )
            raise
        self.logger.info(
            'kind=script provider=notion Workbench publication confirmed.',
            extra={"details": {'page': page_id}},
        )

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
