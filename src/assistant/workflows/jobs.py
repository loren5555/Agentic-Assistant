"""Dispatch finite collection jobs and durable human review signals."""

import json

from dbos import DBOS, DBOSConfiguredInstance, SetWorkflowID

from assistant.config import RuntimeSettings
from assistant.schemas.capture import CaptureBatch, CaptureBrief, CaptureKind, CaptureReceipt, RawCapture
from assistant.schemas.proposal import SourceMaterial, WorkbenchItem
from assistant.services import Services
from assistant.workflows.index import WorkIndex
from assistant.workflows.proposals import ProposalWorkflows, capture_material, digest
from assistant.workflows.recovery import recover
from assistant.workflows.research import ResearchWorkflows


@DBOS.dbos_class()
class JobWorkflows(DBOSConfiguredInstance):
    """Coordinate bounded reads without implementing provider business logic.

    Attributes:
        services: Lazily bound capabilities.
        proposals: Durable proposal and execution operations.
        research: Durable recommendation and feedback operations.
        index: Local pointers to workflow-owned state.
        settings: Batch limits and local runtime configuration.
    """

    def __init__(self, services: Services, proposals: ProposalWorkflows, research: ResearchWorkflows,
                 index: WorkIndex, settings: RuntimeSettings) -> None:
        """Register dependencies before DBOS launches recovery.

        Args:
            services: Provider-facing capabilities.
            proposals: Item-level proposal workflows.
            research: Recommendation workflows.
            index: Local source and cursor index.
            settings: Runtime settings.
        """
        super().__init__("jobs")
        self.services = services
        self.proposals = proposals
        self.research = research
        self.index = index
        self.settings = settings

    @DBOS.step()
    def inputs(self) -> list[SourceMaterial]:
        """Read eligible Inbox and elevated TODO inputs.

        Returns:
            Bounded source snapshots supplied by the input provider.
        """
        sources = self.services.workbench.list_inputs()
        return sources

    @DBOS.step()
    def lookup(self, key: str) -> dict | None:
        """Locate the latest durable owner of one source.

        Args:
            key: Source identity.

        Returns:
            Index metadata, or None for a new input.
        """
        record = self.index.get(key)
        return record

    async def previous(self, key: str) -> tuple[dict | None, dict | None]:
        """Load state through its DBOS event rather than a Notion JSON property.

        Args:
            key: Stable source identity.

        Returns:
            Local pointer and its structured workflow state.
        """
        record = self.lookup(key)
        state = None
        if record is not None:
            state = await DBOS.get_event_async(record["workflow_id"], "state", timeout_seconds=0)
        return record, state

    @DBOS.workflow()
    async def intake(self) -> list[str]:
        """Create proposals and stop at human review, never execute implicitly.

        Returns:
            Verified Workbench links from this pass.
        """
        urls = []
        for source in self.inputs():
            key = f"proposal:{source.kind}:{source.page_id}"
            record, state = await self.previous(key)
            if record is not None and record["fingerprint"] == digest(source.text):
                # A lost acknowledgement must not create another proposal.
                self.proposals.acknowledge(source)
                continue
            previous = WorkbenchItem.model_validate(state["item"]) if state else None
            operation = "intake:" + digest(key + source.text)
            url = await self.proposals.invoke(operation, self.proposals.intake_item, key, source, previous)
            urls.append(url)
        return urls

    @DBOS.step()
    def active(self) -> list[dict]:
        """Read only managed items waiting for review.

        Returns:
            Local active pointers, excluding legacy Notion records.
        """
        records = self.index.active()
        return records

    @DBOS.workflow()
    async def reviews(self) -> list[str]:
        """Dispatch observed human decisions as durable, deduplicated signals.

        Returns:
            Updated Workbench and Interested-follow-up URLs.
        """
        urls = []
        for record in self.active():
            state = await DBOS.get_event_async(record["workflow_id"], "state", timeout_seconds=0)
            saved = WorkbenchItem.model_validate(state["item"])
            current = self.proposals.read_review(saved)
            actionable = (
                current.status == "Open" and current.human_review in {"Approved", "Revision Requested", "Rejected"}
                or current.status == "Executed" and current.result_review in {"Qualified", "Unqualified"}
            )
            if not actionable:
                continue

            # Include the prior owner so repeated human feedback on a redo is a new round.
            signal = {
                "owner": record["workflow_id"], "status": current.status,
                "review": current.human_review, "instruction": current.human_instruction,
                "acceptance": current.result_review, "feedback": current.result_feedback,
                "body": current.body_fingerprint,
            }
            operation = "review:" + digest(json.dumps(signal, sort_keys=True) + current.page_id)
            status = await DBOS.get_workflow_status_async(operation)
            if status is not None and status.status == "ERROR":
                handle = await recover(operation)
            else:
                with SetWorkflowID(operation):
                    handle = await DBOS.start_workflow_async(self.proposals.review_item, record["source_key"], state)
            await DBOS.send_async(operation, signal, topic="review", idempotency_key=operation)
            urls.append(await handle.get_result())

        urls.extend(await self.research.followups())
        return urls

    @DBOS.step()
    def capture_batch(self, kind: CaptureKind) -> CaptureBatch:
        """Read one bounded raw-source page from its saved cursor.

        Args:
            kind: Notero or SimpRead collection.

        Returns:
            Captures and their next continuation token.
        """
        batch = self.services.captures.list_captures(
            kind, self.settings.batch_size, self.index.cursor(kind),
        )
        return batch

    @DBOS.step()
    async def brief(self, capture: RawCapture) -> CaptureBrief:
        """Checkpoint interpretation before any destination write.

        Args:
            capture: Actual source material.

        Returns:
            Grounded destination classification and brief.
        """
        brief = await self.services.briefs.brief(capture)
        return brief

    @DBOS.step()
    def publish_capture(self, capture: RawCapture, brief: CaptureBrief) -> CaptureReceipt:
        """Reject changed scope and recover a verified organized write.

        Args:
            capture: Version assessed by the model.
            brief: Cached paper or knowledge brief.

        Returns:
            Verified destination receipt.
        """
        current = self.services.captures.read_capture(capture.page_id, capture.kind)
        if current.fingerprint != capture.fingerprint:
            raise RuntimeError("Capture changed during briefing; publication stopped")
        receipt = self.services.capture_publisher.publish(capture, brief)
        return receipt

    @DBOS.step()
    async def capture_checkpoint(self, capture: RawCapture, url: str) -> None:
        """Save processed material only after destination verification.

        Args:
            capture: Successfully organized input version.
            url: Verified destination or proposal link.
        """
        await DBOS.set_event_async("capture", {"capture": capture.model_dump(mode="json"), "url": url})
        self.index.save("capture:" + capture.identity, capture.fingerprint, DBOS.workflow_id, url, "Handled")

    @DBOS.step()
    def acknowledge_capture(self, capture: RawCapture) -> None:
        """Mark only SimpRead handled; Notero remains read-only.

        Args:
            capture: Verified source version.
        """
        self.services.captures.mark_handled(capture)

    @DBOS.workflow()
    async def capture_item(self, capture: RawCapture) -> str:
        """Organize one raw record or submit it for approval.

        Args:
            capture: Raw source snapshot.

        Returns:
            Verified organized-output or proposal URL.
        """
        brief = await self.brief(capture)
        if brief.destination == "proposal":
            source = capture_material(capture)
            key = f"proposal:{capture.kind}:{capture.page_id}"
            _, state = await self.previous(key)
            previous = WorkbenchItem.model_validate(state["item"]) if state else None
            operation = "intake:" + digest(key + source.text)
            url = await self.proposals.invoke(operation, self.proposals.intake_item, key, source, previous)
        else:
            receipt = self.publish_capture(capture, brief)
            url = receipt.url
        await self.capture_checkpoint(capture, url)
        self.acknowledge_capture(capture)
        return url

    @DBOS.step()
    def save_cursor(self, kind: str, cursor: str | None) -> None:
        """Advance a collection only after all page operations finish.

        Args:
            kind: Raw collection.
            cursor: Next page token, or None after a complete pass.
        """
        self.index.save_cursor(kind, cursor)

    @DBOS.workflow()
    async def captures(self, kind: CaptureKind, page_id: str | None = None) -> list[str]:
        """Scan bounded raw inputs or explicitly reprocess one source.

        Args:
            kind: Notero or SimpRead collection.
            page_id: Optional explicit raw page identity, including archived articles.

        Returns:
            Verified destination URLs.
        """
        if page_id is None:
            batch = self.capture_batch(kind)
            captures = batch.captures
        else:
            captures = [self.read_capture(page_id, kind)]
        urls = []
        for capture in captures:
            previous = self.lookup("capture:" + capture.identity)
            if previous is not None and previous["fingerprint"] == capture.fingerprint:
                self.acknowledge_capture(capture)
                continue
            operation = "capture:" + digest(capture.identity + capture.fingerprint)
            url = await self.proposals.invoke(operation, self.capture_item, capture)
            urls.append(url)
        if page_id is None:
            self.save_cursor(kind, batch.next_cursor)
        return urls

    @DBOS.step()
    def read_capture(self, page_id: str, kind: CaptureKind) -> RawCapture:
        """Read an explicitly selected raw capture.

        Args:
            page_id: Raw Notion page identifier.
            kind: Expected collection.

        Returns:
            Current source material.
        """
        capture = self.services.captures.read_capture(page_id, kind)
        return capture

    @DBOS.workflow()
    async def dispatch(self, job: str, day: str, page_id: str | None = None):
        """Run one named job and return its actual outputs.

        Args:
            job: Intake, reviews, papers, articles, or recommendations.
            day: Asia/Shanghai date used for daily recommendation identity.
            page_id: Optional raw capture for manual reprocessing.

        Returns:
            Job links or an evidence-grounded recommendation report.
        """
        if job == "intake":
            output = await self.intake()
        elif job == "reviews":
            output = await self.reviews()
        elif job in {"papers", "articles"}:
            kind = "notero" if job == "papers" else "simpread"
            output = await self.captures(kind, page_id)
        elif job == "recommendations":
            mode = "demo" if self.services.config.providers.discovery == "demo" else "real"
            output = await self.proposals.invoke(f"recommendations:{mode}:{day}", self.research.recommendations, day)
        else:
            raise ValueError(f"Unknown job: {job}")
        return output
