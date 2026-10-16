"""Checkpoint item-level work without storing machine payloads in Notion."""

import hashlib
import json
from pathlib import Path

from dbos import DBOS, DBOSConfiguredInstance, SetWorkflowID

from assistant.actions import INBOX_CANDIDATES
from assistant.schemas.investigation import InvestigationRequest
from assistant.schemas.proposal import Proposal, ProposedTask, SourceMaterial, WorkbenchItem
from assistant.schemas.routing import RouterDecision, RouterInput
from assistant.schemas.curation import ArchiveReceipt, CurationDecision, RetainedArtifact
from assistant.schemas.task import TaskResult
from assistant.schemas.capture import RawCapture
from assistant.services import Services
from assistant.workflows.index import WorkIndex
from assistant.workflows.recovery import recover


def digest(value: str) -> str:
    """Compute a stable execution or publication identity.

    Args:
        value: Canonical material identifying one operation.

    Returns:
        SHA-256 digest.
    """
    key = hashlib.sha256(value.encode()).hexdigest()
    return key


def capture_material(capture: RawCapture) -> SourceMaterial:
    """Adapt meaningful capture content without losing metadata-only evidence.

    Args:
        capture: Raw title, body, and metadata from Notero or SimpRead.

    Returns:
        Vendor-neutral source material suitable for proposal drafting.
    """
    text = json.dumps(
        {"title": capture.title, "text": capture.text, "metadata": capture.metadata},
        ensure_ascii=False, sort_keys=True,
    )
    source = SourceMaterial(
        kind=capture.kind, page_id=capture.page_id, url=capture.url,
        title=capture.title, text=text, revision=capture.revision,
    )
    return source


@DBOS.dbos_class()
class ProposalWorkflows(DBOSConfiguredInstance):
    """Own durable intake, reviewed execution, and accepted-result curation.

    Attributes:
        services: Replaceable role and storage capabilities.
        index: Local lookup metadata pointing to DBOS state events.
        directory: Local process-report directory.
    """

    def __init__(self, services: Services, index: WorkIndex, directory: Path) -> None:
        """Bind dependencies and register the stable DBOS instance name.

        Args:
            services: Lazy provider implementations.
            index: Application-owned lookup store.
            directory: Location for detailed runtime reports.
        """
        super().__init__("proposals")
        self.services = services
        self.index = index
        self.directory = directory

    @DBOS.step()
    async def checkpoint(self, key: str, source: SourceMaterial, item: WorkbenchItem) -> None:
        """Save machine state in DBOS before advancing its local index pointer.

        Args:
            key: Stable raw input identity.
            source: Input scope represented by the proposal.
            item: Current report, deliverable, extraction, and human decisions.
        """
        state = {"source": source.model_dump(mode="json"), "item": item.model_dump(mode="json")}
        traces = {"proposal": item.proposal.process if item.proposal else None, "result": item.result.process if item.result else None}
        report_directory = self.directory / "process"
        report_directory.mkdir(parents=True, exist_ok=True)
        traces = {name: value.model_dump(mode="json") for name, value in traces.items() if value is not None}
        if traces:
            path = report_directory / f"{digest(DBOS.workflow_id)}.json"
            path.write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
        await DBOS.set_event_async("state", state)
        self.index.save(key, digest(source.text), DBOS.workflow_id, item.page_id, item.status)

    @DBOS.step()
    def read_source(self, source: SourceMaterial) -> SourceMaterial:
        """Refresh the raw input while respecting independent source interfaces.

        Args:
            source: Source identity retained in DBOS.

        Returns:
            Current meaningful source material.
        """
        current = self.current_source(source)
        return current

    def current_source(self, source: SourceMaterial) -> SourceMaterial:
        """Read live scope without reusing an earlier checkpoint during writes.

        Args:
            source: Raw input identity.

        Returns:
            Current material for an authorization comparison.
        """
        if source.kind in {"notero", "simpread"}:
            capture = self.services.captures.read_capture(source.page_id, source.kind)
            current = capture_material(capture)
        else:
            current = self.services.workbench.read_source(source.url)
        return current

    @DBOS.step()
    def read_review(self, saved: WorkbenchItem) -> WorkbenchItem:
        """Combine live human fields with the runtime-owned structured payload.

        Args:
            saved: Last verified runtime snapshot.

        Returns:
            Current review state retaining local proposal and result data.
        """
        current = self.services.workbench.read_item(saved.page_id)
        current.proposal = saved.proposal
        current.result = saved.result
        current.curation = saved.curation
        current.source_kind = saved.source_kind
        return current

    @DBOS.step()
    async def draft(self, source: SourceMaterial, previous: WorkbenchItem | None = None) -> Proposal:
        """Checkpoint one provider draft separately from external publication.

        Args:
            source: Grounded input material.
            previous: Report and human feedback when revising.

        Returns:
            Provider-generated proposal.
        """
        proposal = await self.services.proposer.draft(source, previous)
        return proposal

    @DBOS.step()
    def publish_proposal(self, source: SourceMaterial, proposal: Proposal, previous: WorkbenchItem | None = None) -> WorkbenchItem:
        """Publish and re-fetch one proposal without machine Notion properties.

        Args:
            source: Original input.
            proposal: Checkpointed draft.
            previous: Workbench item when updating rather than creating.

        Returns:
            Verified page retaining the runtime payload.
        """
        if self.current_source(source).text != source.text:
            raise RuntimeError("Source changed during proposal drafting")
        if previous is None:
            item = self.services.workbench.submit(source, proposal, DBOS.workflow_id)
        else:
            current = self.services.workbench.read_item(previous.page_id)
            expected_key = "proposal:" + digest(proposal.model_dump_json(exclude={"process"}))
            if current.publication_key == expected_key and current.publication_applied and current.status == "Open":
                item = self.services.workbench.revise(previous, proposal)
            else:
                fields = ("human_review", "human_instruction", "result_review", "result_feedback")
                partial = current.publication_key == expected_key
                checked = ("human_instruction", "result_feedback") if partial else fields
                if any(getattr(current, field) != getattr(previous, field) for field in checked):
                    raise RuntimeError("Human review changed during proposal drafting")
                if current.body_fingerprint != previous.body_fingerprint and current.publication_key != expected_key:
                    raise RuntimeError("Report changed during proposal drafting")
                if self.current_source(source).text != source.text:
                    raise RuntimeError("Source changed during proposal drafting")
                item = self.services.workbench.revise(previous, proposal)
        item.proposal = proposal
        item.source_kind = source.kind
        return item

    @DBOS.step()
    def acknowledge(self, source: SourceMaterial) -> None:
        """Close raw intake only after its destination is verified.

        Args:
            source: Original source to acknowledge.
        """
        if source.kind in {"inbox", "todo"}:
            if self.current_source(source).text != source.text:
                raise RuntimeError("Source changed before intake acknowledgement")
            self.services.workbench.close_source(source)
        elif source.kind == "simpread":
            capture = self.services.captures.read_capture(source.page_id, source.kind)
            if capture_material(capture).text != source.text:
                raise RuntimeError("Capture changed before proposal acknowledgement")
            self.services.captures.mark_handled(capture)

    @DBOS.workflow()
    async def intake_item(self, key: str, source: SourceMaterial, previous: WorkbenchItem | None = None) -> str:
        """Publish one source proposal and end at the human approval boundary.

        Args:
            key: Stable raw input key.
            source: Captured material for this intake version.
            previous: Existing managed report if this input is being reorganized.

        Returns:
            Verified Workbench URL.
        """
        proposal = await self.draft(source, previous)
        item = self.publish_proposal(source, proposal, previous)
        await self.checkpoint(key, source, item)
        self.acknowledge(source)
        return item.url

    @DBOS.step()
    def route(self, task: ProposedTask, source: SourceMaterial) -> RouterInput:
        """Build the execution request independently of the routing provider.

        Args:
            task: Approved scope and human instructions.
            source: Original input.

        Returns:
            Router input with available executable capabilities.
        """
        request = RouterInput(
            text=task.model_dump_json(exclude={"proposal": {"process"}}),
            context=[source.text], candidates=INBOX_CANDIDATES,
        )
        return request

    @DBOS.step()
    async def decide(self, request: RouterInput) -> RouterDecision:
        """Checkpoint routing separately from task execution.

        Args:
            request: Approved task and available actions.

        Returns:
            Selected capability and reasoning.
        """
        decision = await self.services.router.decide(request)
        return decision

    @DBOS.step()
    async def execute(self, task: ProposedTask, source: SourceMaterial, decision: RouterDecision) -> TaskResult:
        """Checkpoint the actual deliverable before its Notion write.

        Args:
            task: Approved scope.
            source: Original grounded content.
            decision: Selected executable action.

        Returns:
            Completed deliverable with provider telemetry.
        """
        action = decision.selected_action_id
        if action == "investigate_question":
            request = InvestigationRequest(question=task.proposal.action, context=[source.text, task.instruction])
            report = await self.services.investigator.investigate(request)
            sections = [report.answer]
            sections.extend(f"- [{e.title}]({e.url}): {e.finding}" for e in report.sources)
            sections.extend(report.limitations)
            result = TaskResult(content="\n\n".join(sections), process=report.process)
        elif action in {"complete_task", "organize_material"}:
            task.instruction += f"\n\nOriginal material:\n{source.text}"
            result = await self.services.worker.execute(task)
        else:
            raise ValueError(f"Unsupported executable action: {action}")
        result.action_id = action
        return result

    @DBOS.step()
    def save_result(self, source: SourceMaterial, item: WorkbenchItem, result: TaskResult) -> WorkbenchItem:
        """Recheck authorization live and verify the human-facing result write.

        Args:
            source: Executed source scope.
            item: Human decision snapshot authorizing execution.
            result: Checkpointed deliverable.

        Returns:
            Current page with the new result and pending acceptance.
        """
        current = self.services.workbench.read_item(item.page_id)
        expected_key = "result:" + digest(result.content)
        if current.publication_key == expected_key and current.status == "Executed":
            # Recover a completed write without resetting a subsequent human review.
            self.services.workbench.save_result(item, result)
            current.proposal = item.proposal
            current.source_kind = item.source_kind
            current.result = result
            return current
        if current.publication_key == expected_key:
            item.body_fingerprint = current.body_fingerprint
        self.check_authorization(source, item)
        self.services.workbench.save_result(item, result)
        current = self.services.workbench.read_item(item.page_id)
        current.proposal = item.proposal
        current.source_kind = item.source_kind
        current.result = result
        return current

    def check_authorization(self, source: SourceMaterial, item: WorkbenchItem) -> None:
        """Read authorization inside each write step, including retries.

        Args:
            source: Scope that must remain unchanged.
            item: Approval or acceptance snapshot used by the operation.
        """
        current = self.services.workbench.read_item(item.page_id)
        current_source = self.current_source(source)
        fields = ("status", "human_review", "human_instruction", "result_review", "result_feedback", "body_fingerprint")
        if current_source.text != source.text or any(getattr(current, field) != getattr(item, field) for field in fields):
            raise RuntimeError("Source, report, or human authorization changed; publication stopped")

    @DBOS.step()
    async def extract(self, item: WorkbenchItem) -> CurationDecision:
        """Checkpoint grounded extraction before archive writes.

        Args:
            item: Human-accepted result.

        Returns:
            Current extraction decision.
        """
        decision = await self.services.curator.extract(item)
        return decision

    @DBOS.step()
    def publish_artifact(self, source: SourceMaterial, item: WorkbenchItem, artifact: RetainedArtifact, key: str) -> ArchiveReceipt:
        """Verify acceptance immediately before one retry-safe archive write.

        Args:
            source: Original input scope.
            item: Accepted result.
            artifact: Reusable material grounded in that result.
            key: Stable publication identifier.

        Returns:
            Verified archive receipt.
        """
        self.check_authorization(source, item)
        receipt = self.services.archive.publish(item, artifact, key)
        return receipt

    @DBOS.step()
    def close_item(self, source: SourceMaterial, item: WorkbenchItem, status: str) -> None:
        """Verify current review before applying a terminal visible status.

        Args:
            source: Original source version.
            item: Last human decision snapshot.
            status: Deprecated, Finished, or Archived.
        """
        current = self.services.workbench.read_item(item.page_id)
        if current.status == status:
            return
        self.check_authorization(source, item)
        self.services.workbench.set_status(item, status)

    @DBOS.workflow()
    async def review_item(self, key: str, state: dict) -> str:
        """Consume one durable review signal and end at the next human boundary.

        Args:
            key: Source identity used by the local index.
            state: Previous checkpoint containing source and report payloads.

        Returns:
            Current Workbench URL.
        """
        signal = await DBOS.recv_async(topic="review", timeout_seconds=60)
        if signal is None:
            raise TimeoutError("Review signal was not delivered")
        source = SourceMaterial.model_validate(state["source"])
        saved = WorkbenchItem.model_validate(state["item"])
        item = self.read_review(saved)
        current_source = self.read_source(source)

        # Source edits require a new proposal; approval never carries across scope.
        changed = current_source.text != source.text
        if item.human_review != "Rejected" and (changed or (item.status == "Open" and item.human_review == "Revision Requested")):
            proposal = await self.draft(current_source, item)
            item = self.publish_proposal(current_source, proposal, item)
            await self.checkpoint(key, current_source, item)
            return item.url

        if item.status == "Open" and item.human_review == "Rejected":
            self.close_item(current_source, item, "Deprecated")
            item.status = "Deprecated"
        elif item.status == "Open" and item.human_review == "Approved" or item.status == "Executed" and item.result_review == "Unqualified":
            if item.body_fingerprint != saved.body_fingerprint:
                raise RuntimeError("Report was edited outside the workflow; request a proposal revision")
            instructions = "\n\n".join([item.human_instruction, item.result_feedback])
            if item.result is not None:
                instructions += f"\n\nPrevious result:\n{item.result.content}"
            task = ProposedTask(workbench_url=item.url, proposal=item.proposal, instruction=instructions, redo=item.status == "Executed")
            request = self.route(task, source)
            decision = await self.decide(request)
            if decision.selected_action_id == "ask_user":
                question = decision.clarification_question or decision.suggested_next_step
                self.request_input(source, item, question)
                item = self.read_review(item)
            else:
                result = await self.execute(task, source, decision)
                item = self.save_result(source, item, result)
        elif item.status == "Executed" and item.result_review == "Qualified":
            if item.body_fingerprint != saved.body_fingerprint:
                raise RuntimeError("Result report changed; rerun execution before curation")
            decision = await self.extract(item)
            for position, artifact in enumerate(decision.artifacts):
                identity = f"{item.page_id}:{item.proposal.version}:{digest(item.result.content)}:{position}:{artifact.model_dump_json()}"
                archive_key = digest(identity)
                receipt = self.publish_artifact(source, item, artifact, archive_key)
                decision.receipts.append(receipt)
            item.curation = decision
            status = "Archived" if decision.artifacts else "Finished"
            self.close_item(source, item, status)
            item.status = status

        await self.checkpoint(key, source, item)
        return item.url

    @DBOS.step()
    def request_input(self, source: SourceMaterial, item: WorkbenchItem, question: str) -> None:
        """Publish a clarification only while its authorization remains current.

        Args:
            source: Original input scope.
            item: Approved proposal awaiting necessary personal information.
            question: Focused user-owned choice or missing material.
        """
        current = self.services.workbench.read_item(item.page_id)
        expected_key = "clarification:" + digest(question)
        if current.publication_key == expected_key and current.publication_applied:
            self.services.workbench.request_input(item, question)
            return
        if current.publication_key == expected_key:
            item.body_fingerprint = current.body_fingerprint
            item.human_review = current.human_review
            item.status = current.status
        self.check_authorization(source, item)
        self.services.workbench.request_input(item, question)

    async def invoke(self, workflow_id: str, function, *args):
        """Reuse an operation identity and resume its incomplete steps on retry.

        Args:
            workflow_id: Deterministic operation identity.
            function: Registered workflow method.
            args: Serializable business inputs.

        Returns:
            Completed workflow output.
        """
        status = await DBOS.get_workflow_status_async(workflow_id)
        if status is not None and status.status == "ERROR":
            handle = await recover(workflow_id)
        else:
            with SetWorkflowID(workflow_id):
                handle = await DBOS.start_workflow_async(function, *args)
        output = await handle.get_result()
        return output
