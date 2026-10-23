"""Run reviews: advance managed work according to explicit human decisions.

Inputs:
    Active local index entries, their DBOS state, current Workbench properties,
    source content, and human approval, acceptance, instructions, and feedback.

Outputs:
    Updated Workbench URLs and state checkpoints. Qualified retained outcomes
    produce archive links; Interested Research Feed entries produce Inbox links.

Workflow:
    Inspect managed Open/Executed items -> send a durable review signal -> read
    current scope and human decisions. Revision Requested or source edits invoke
    proposal revision; Rejected becomes Deprecated. Approved work is routed to
    a worker/investigator, or asks the user, then awaits result acceptance.
    Unqualified work is redone. Qualified work is curated and becomes Archived
    after retained artifacts are published, or Finished if none are retained.
    Interested follow-ups are processed after the Workbench pass.

Participants and effects:
    Human approver/reviewer, decision router, execution worker, investigator,
    curator, Workbench, ArchiveStore, and ResearchFeed. run reviews and schedules
    use this task. It calls models, publishes results, and records durable state.

Boundaries:
    Unmanaged historical rows are not automatically adopted. Source and human
    authorization are reread at write boundaries; publication receipts identify
    report versions. Follow-ups never write directly to Papers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import json

from dbos import DBOS, SetWorkflowID

from assistant.components.archive.models import ArchiveReceipt
from assistant.components.curator.models import CurationDecision, RetainedArtifact
from assistant.components.inputs.models import SourceMaterial
from assistant.components.investigator.models import InvestigationRequest
from assistant.components.router.actions import EXECUTION_ACTIONS
from assistant.components.router.models import RouterDecision, RouterInput
from assistant.components.task_worker.models import TaskRequest, TaskResult
from assistant.components.workbench.models import WorkbenchItem
from assistant.runtime.records import digest
from assistant.runtime.recovery import check_version, recover
from logger import get_logger

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows, WorkbenchWorkflows
    from assistant.workflows.tasks.recommend_papers import RecommendationWorkflows

logger = get_logger("assistant.workflows.tasks.process_reviews")


@DBOS.workflow(name="JobWorkflows.reviews")
async def process_reviews(self: TaskWorkflows) -> list[str]:
    """Dispatch observed human decisions as durable, deduplicated signals.

    Returns:
        Updated Workbench and Interested-follow-up URLs.
    """
    urls = []
    records = self.list_active()
    waiting = 0
    for position, record in enumerate(records, start=1):
        logger.info("Review item %d/%d: page=%s owner=%s.",
                    position, len(records), record["page_id"], record["workflow_id"])
        state = await DBOS.get_event_async(record["workflow_id"], "state", timeout_seconds=0)
        saved = WorkbenchItem.model_validate(state["item"])
        current = self.proposals.read_review(saved)
        actionable = (
            current.status == "Open" and current.human_review in {"Approved", "Revision Requested", "Rejected"}
            or current.status == "Executed" and current.result_review in {"Qualified", "Unqualified"}
        )
        if not actionable:
            waiting += 1
            logger.info("Waiting for human review: page=%s status=%s approval=%s acceptance=%s.",
                        current.page_id, current.status, current.human_review, current.result_review)
            continue
        logger.info("Dispatching human decision: page=%s status=%s approval=%s acceptance=%s.",
                    current.page_id, current.status, current.human_review, current.result_review)

        # Include the prior owner so repeated human feedback on a redo is a new round.
        signal = {
            "owner": record["workflow_id"], "status": current.status,
            "review": current.human_review, "instruction": current.human_instruction,
            "acceptance": current.result_review, "feedback": current.result_feedback,
            "publication": current.publication_key,
        }
        operation = "review:" + digest(json.dumps(signal, sort_keys=True) + current.page_id)
        status = await DBOS.get_workflow_status_async(operation)
        if status is not None:
            check_version(status)
        if status is not None and status.status == "ERROR":
            handle = await recover(operation)
        elif status is not None:
            logger.info("kind=checkpoint Reusing existing review workflow: workflow=%s status=%s.",
                        operation, status.status)
            handle = await DBOS.retrieve_workflow_async(operation, existing_workflow=False)
        else:
            with SetWorkflowID(operation):
                handle = await DBOS.start_workflow_async(self.proposals.review_item, record["source_key"], state)
        await DBOS.send_async(operation, signal, topic="review", idempotency_key=operation)
        urls.append(await handle.get_result())

    followups = await self.research.process_followups()
    logger.info("Reviews completed: inspected=%d advanced_or_reused=%d waiting=%d interested_followups=%d.",
                len(records), len(urls), waiting, len(followups))
    urls.extend(followups)
    return urls


@DBOS.workflow(name="ProposalWorkflows.review_item")
async def review_item(self: WorkbenchWorkflows, key: str, state: dict) -> str:
    """Consume one durable review signal and end at the next human boundary.

    Args:
        key: Source identity used by the local index.
        state: Previous checkpoint containing source and report payloads.

    Returns:
        Current Workbench URL.
    """
    logger.info("Review workflow awaiting durable decision signal: workflow=%s.", DBOS.workflow_id)
    signal = await DBOS.recv_async(topic="review", timeout_seconds=60)
    if signal is None:
        raise TimeoutError("Review signal was not delivered")
    source = SourceMaterial.model_validate(state["source"])
    saved = WorkbenchItem.model_validate(state["item"])
    item = self.read_review(saved)
    current_source = self.read_source(source)

    # Source edits require a new proposal; approval never carries across scope.
    changed = current_source.text != source.text
    logger.info("Review scope checked: page=%s source_changed=%s.", item.page_id, changed)
    if item.human_review != "Rejected" and (changed or (item.status == "Open" and item.human_review == "Revision Requested")):
        logger.info("Revising proposal before further action: page=%s source_changed=%s.", item.page_id, changed)
        proposal = await self.draft(current_source, item)
        item = self.publish_proposal(current_source, proposal, item)
        await self.save_checkpoint(key, current_source, item)
        logger.info("Revision completed: page=%s; waiting for fresh approval.", item.page_id)
        return item.url

    if item.status == "Open" and item.human_review == "Rejected":
        logger.info("Applying human rejection: page=%s.", item.page_id)
        self.close_item(current_source, item, "Deprecated")
        item.status = "Deprecated"
    elif item.status == "Open" and item.human_review == "Approved" or item.status == "Executed" and item.result_review == "Unqualified":
        if item.publication_key != saved.publication_key:
            raise RuntimeError("Report publication changed; request a proposal revision")
        instructions = "\n\n".join([item.human_instruction, item.result_feedback])
        if item.result is not None:
            instructions += f"\n\nPrevious result:\n{item.result.content}"
        task = TaskRequest(workbench_url=item.url, proposal=item.proposal, instruction=instructions, redo=item.status == "Executed")
        request = self.route(task, source)
        decision = await self.decide(request)
        if decision.selected_action_id == "ask_user":
            logger.info("Execution requires user input: page=%s; returning to Pending.", item.page_id)
            question = decision.clarification_question or decision.suggested_next_step
            self.request_input(source, item, question)
            item = self.read_review(item)
        else:
            result = await self.execute(task, source, decision)
            item = self.save_result(source, item, result)
    elif item.status == "Executed" and item.result_review == "Qualified":
        if item.publication_key != saved.publication_key:
            raise RuntimeError("Result publication changed; rerun execution before curation")
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

    await self.save_checkpoint(key, source, item)
    logger.info("Review workflow completed: page=%s status=%s workflow=%s.", item.page_id, item.status, DBOS.workflow_id)
    return item.url


@DBOS.step(name="JobWorkflows.active")
def list_active(self: TaskWorkflows) -> list[dict]:
    """Read only managed items waiting for review.

    Returns:
        Local active pointers, excluding legacy Notion records.
    """
    records = self.index.list_active()
    logger.info("Loaded %d managed Open/Executed Workbench items from the local index.", len(records))
    return records


@DBOS.step(name="ProposalWorkflows.read_review")
def read_review(self: WorkbenchWorkflows, saved: WorkbenchItem) -> WorkbenchItem:
    """Combine live human fields with the runtime-owned structured payload.

    Args:
        saved: Last verified runtime snapshot.

    Returns:
        Current review state retaining local proposal and result data.
    """
    logger.info("Reading current human review: page=%s.", saved.page_id)
    current = self.services.workbench.read_item(saved.page_id)
    current.proposal = saved.proposal
    current.result = saved.result
    current.curation = saved.curation
    current.source_kind = saved.source_kind
    logger.info("Human review read: page=%s status=%s approval=%s acceptance=%s.",
                current.page_id, current.status, current.human_review, current.result_review)
    return current


@DBOS.step(name="ProposalWorkflows.route")
def route(self: WorkbenchWorkflows, task: TaskRequest, source: SourceMaterial) -> RouterInput:
    """Build the execution request independently of the routing provider.

    Args:
        task: Approved scope and human instructions.
        source: Original input.

    Returns:
        Router input with available executable capabilities.
    """
    request = RouterInput(
        text=task.model_dump_json(exclude={"proposal": {"process"}}),
        context=[source.text], candidates=EXECUTION_ACTIONS,
    )
    return request


@DBOS.step(name="ProposalWorkflows.decide")
async def decide(self: WorkbenchWorkflows, request: RouterInput) -> RouterDecision:
    """Checkpoint routing separately from task execution.

    Args:
        request: Approved task and available actions.

    Returns:
        Selected capability and reasoning.
    """
    logger.info("Requesting execution route: candidates=%d input_characters=%d.", len(request.candidates), len(request.text))
    decision = await self.services.router.decide(request)
    logger.info("Execution route selected: action=%s clarification=%s.",
                decision.selected_action_id, decision.clarification_question is not None)
    return decision


@DBOS.step(name="ProposalWorkflows.execute")
async def execute(self: WorkbenchWorkflows, task: TaskRequest, source: SourceMaterial, decision: RouterDecision) -> TaskResult:
    """Checkpoint the actual deliverable before its Notion write.

    Args:
        task: Approved scope.
        source: Original grounded content.
        decision: Selected executable action.

    Returns:
        Completed deliverable with provider telemetry.
    """
    action = decision.selected_action_id
    logger.info("Executing approved task: workbench=%s action=%s redo=%s.", task.workbench_url, action, task.redo)
    if action == "investigate_question":
        logger.info("Dispatching approved action: action=%s capability=investigator.", action)
        request = InvestigationRequest(question=task.proposal.action, context=[source.text, task.instruction])
        report = await self.services.investigator.investigate(request)
        sections = [report.answer]
        sections.extend(f"- [{e.title}]({e.url}): {e.finding}" for e in report.sources)
        sections.extend(report.limitations)
        result = TaskResult(content="\n\n".join(sections), process=report.process)
    elif action in {"complete_task", "organize_material"}:
        logger.info("Dispatching approved action: action=%s capability=task_worker.", action)
        task.instruction += f"\n\nOriginal material:\n{source.text}"
        result = await self.services.worker.execute(task)
    else:
        raise ValueError(f"Unsupported executable action: {action}")
    result.action_id = action
    logger.info("Task execution completed: workbench=%s action=%s result_characters=%d.", task.workbench_url, action, len(result.content))
    return result


@DBOS.step(name="ProposalWorkflows.save_result")
def save_result(self: WorkbenchWorkflows, source: SourceMaterial, item: WorkbenchItem, result: TaskResult) -> WorkbenchItem:
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
        logger.info("Recovered verified execution result: page=%s status=%s; no model rerun required.", item.page_id, current.status)
        return current
    self.check_authorization(source, item)
    self.services.workbench.save_result(item, result)
    current = self.services.workbench.read_item(item.page_id)
    current.proposal = item.proposal
    current.source_kind = item.source_kind
    current.result = result
    logger.info("Execution result publication verified: page=%s status=%s.", current.page_id, current.status)
    return current


@DBOS.step(name="ProposalWorkflows.request_input")
def request_input(self: WorkbenchWorkflows, source: SourceMaterial, item: WorkbenchItem, question: str) -> None:
    """Publish a clarification only while its authorization remains current.

    Args:
        source: Original input scope.
        item: Approved proposal awaiting necessary personal information.
        question: Focused user-owned choice or missing material.
    """
    logger.info("Publishing clarification request: page=%s question_characters=%d.", item.page_id, len(question))
    current = self.services.workbench.read_item(item.page_id)
    expected_key = "clarification:" + digest(question)
    if current.publication_key == expected_key and current.publication_applied:
        self.services.workbench.request_input(item, question)
        return
    self.check_authorization(source, item)
    self.services.workbench.request_input(item, question)


@DBOS.step(name="ProposalWorkflows.extract")
async def extract(self: WorkbenchWorkflows, item: WorkbenchItem) -> CurationDecision:
    """Checkpoint grounded extraction before archive writes.

    Args:
        item: Human-accepted result.

    Returns:
        Current extraction decision.
    """
    logger.info("Curating accepted result: page=%s.", item.page_id)
    decision = await self.services.curator.extract(item)
    logger.info("Curation completed: page=%s retained_artifacts=%d.", item.page_id, len(decision.artifacts))
    return decision


@DBOS.step(name="ProposalWorkflows.publish_artifact")
def publish_artifact(self: WorkbenchWorkflows, source: SourceMaterial, item: WorkbenchItem, artifact: RetainedArtifact, key: str) -> ArchiveReceipt:
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
    logger.info("Publishing retained artifact: workbench_page=%s destination=%s title=%r.", item.page_id, artifact.kind, artifact.title[:120])
    receipt = self.services.archive.publish(item, artifact, key)
    logger.info("Retained artifact verified: workbench_page=%s url=%s.", item.page_id, receipt.url)
    return receipt


@DBOS.step(name="ProposalWorkflows.close_item")
def close_item(self: WorkbenchWorkflows, source: SourceMaterial, item: WorkbenchItem, status: str) -> None:
    """Verify current review before applying a terminal visible status.

    Args:
        source: Original source version.
        item: Last human decision snapshot.
        status: Deprecated, Finished, or Archived.
    """
    current = self.services.workbench.read_item(item.page_id)
    if current.status == status:
        logger.info("Terminal status already applied: page=%s status=%s.", item.page_id, status)
        return
    self.check_authorization(source, item)
    self.services.workbench.set_status(item, status)
    logger.info("Workbench finalized: page=%s status=%s.", item.page_id, status)


def check_authorization(self: WorkbenchWorkflows, source: SourceMaterial, item: WorkbenchItem) -> None:
    """Read authorization inside each write step, including retries.

    Args:
        source: Scope that must remain unchanged.
        item: Approval or acceptance snapshot used by the operation.
    """
    current = self.services.workbench.read_item(item.page_id)
    current_source = self.read_current_source(source)
    fields = ("status", "human_review", "human_instruction", "result_review", "result_feedback", "publication_key")
    if current_source.text != source.text or any(getattr(current, field) != getattr(item, field) for field in fields):
        raise RuntimeError("Source, publication, or human authorization changed; publication stopped")


@DBOS.workflow(name="ResearchWorkflows.followups")
async def process_followups(self: RecommendationWorkflows) -> list[str]:
    """Turn Interested reviews into Inbox entries with checkpointed writes.

    Returns:
        Verified newly handled Inbox links.
    """
    urls = []
    records = self.list_interested()
    for position, record in enumerate(records, start=1):
        logger.info("Interested entry %d/%d: feed_page=%s.", position, len(records), record["id"])
        url = self.create_follow_up(record["id"])
        if url:
            urls.append(url)
    await DBOS.set_event_async("followups", urls)
    logger.info("Interested follow-ups completed: inspected=%d verified_or_reused=%d skipped=%d.",
                len(records), len(urls), len(records) - len(urls))
    return urls


@DBOS.step(name="ResearchWorkflows.list_interested")
def list_interested(self: RecommendationWorkflows) -> list[dict[str, str]]:
    """Read human feedback without changing it.

    Returns:
        Feed identities approved for one Inbox follow-up.
    """
    logger.info("Reading Interested Research Feed entries for Inbox follow-up.")
    records = self.services.feed.list_interested()
    logger.info("Read %d Interested Feed entries.", len(records))
    return records


@DBOS.step(name="ResearchWorkflows.create_follow_up")
def create_follow_up(self: RecommendationWorkflows, feed_page_id: str) -> str:
    """Publish one verified Inbox follow-up, never a Papers record.

    Args:
        feed_page_id: Interested recommendation identity.

    Returns:
        Verified Inbox URL, or empty string for withdrawn or previously handled feedback.
    """
    key = f"research-follow-up:{feed_page_id}"
    previous = self.index.get(key)
    if previous is not None:
        logger.info("Skipping already handled Interested entry: feed_page=%s.", feed_page_id)
        return ""
    url = self.services.feed.create_follow_up(feed_page_id)
    if url:
        self.index.save(key, feed_page_id, DBOS.workflow_id, url, "Handled")
        logger.info("Interested follow-up verified: feed_page=%s inbox=%s.", feed_page_id, url)
    else:
        logger.info("Interested entry required no new follow-up: feed_page=%s; withdrawn or already submitted.", feed_page_id)
    return url
