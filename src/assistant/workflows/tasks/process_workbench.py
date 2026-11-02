"""Run process-workbench: advance managed work according to explicit human decisions.

Input origin:
    commands/run.dispatch selects process-workbench. WorkIndex identifies managed entries;
    DBOS supplies structured proposal/result state, and Workbench supplies live
    approval, acceptance, and feedback. InputSource/capture readers refresh the
    original source; Research Feed supplies Interested recommendations.

Output destination:
    Approved work flows through Router to TaskWorker/Investigator and back into
    Workbench. Revisions flow through Proposer to Workbench. Accepted useful
    outcomes flow through Curator and ArchiveStore to Knowledge/Ideas, with final
    status back in Workbench. Interested follow-ups go to Inbox for propose-tasks.
    DBOS/index retain progress; destination links return to dispatch.

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
    curator, Workbench, ArchiveStore, and ResearchFeed. run process-workbench and schedules
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
from assistant.components.workbench.models import WorkbenchItem, result_publication_key
from assistant.runtime.records import digest
from assistant.runtime.recovery import check_version, recover
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows, WorkbenchWorkflows
    from assistant.workflows.tasks.recommend_papers import RecommendationWorkflows

logger = get_logger("assistant.workflows.tasks.process_workbench")


@DBOS.workflow(name="JobWorkflows.reviews")
@trace_call("workflow", "process_workbench")
async def process_workbench(self: TaskWorkflows) -> list[str]:
    """Dispatch observed human decisions as durable, deduplicated signals.

    Returns:
        Updated Workbench and Interested-follow-up URLs.
    """
    urls = []
    records = self.list_active()
    waiting = 0
    for position, record in enumerate(records, start=1):
        state = await DBOS.get_event_async(record["workflow_id"], "state", timeout_seconds=0)
        saved = WorkbenchItem.model_validate(state["item"])
        logger.info(
            'Review item %d/%d: title=%r.',
            position,
            len(records),
            saved.title,
            extra={"details": {'page': record['page_id'], 'owner': record['workflow_id']}},
        )
        current = self.proposals.read_review(saved)
        actionable = (
            current.status == "Open" and current.human_review in {"Approved", "Revision Requested", "Rejected"}
            or current.status == "Executed" and current.result_review in {"Qualified", "Unqualified"}
        )
        if not actionable:
            waiting += 1
            logger.info(
                'Waiting for human review: title=%r status=%s approval=%s acceptance=%s.',
                current.title,
                current.status,
                current.human_review,
                current.result_review,
                extra={"details": {'page': current.page_id}},
            )
            continue
        logger.info(
            'Dispatching human decision: title=%r status=%s approval=%s acceptance=%s.',
            current.title,
            current.status,
            current.human_review,
            current.result_review,
            extra={"details": {'page': current.page_id}},
        )

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
            logger.info(
                'kind=checkpoint Reusing existing review workflow: title=%r status=%s.',
                current.title,
                status.status,
                extra={"details": {'workflow': operation}},
            )
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
@trace_call("workflow", "review_item")
async def review_item(self: WorkbenchWorkflows, key: str, state: dict) -> str:
    """Consume one durable review signal and end at the next human boundary.

    Args:
        key: Source identity used by the local index.
        state: Previous checkpoint containing source and report payloads.

    Returns:
        Current Workbench URL.
    """
    logger.info(
        'Review workflow awaiting durable decision signal: title=%r.',
        state["item"]["title"],
        extra={"details": {'workflow': DBOS.workflow_id}},
    )
    signal = await DBOS.recv_async(topic="review", timeout_seconds=60)
    if signal is None:
        raise TimeoutError("Review signal was not delivered")
    source = SourceMaterial.model_validate(state["source"])
    saved = WorkbenchItem.model_validate(state["item"])
    item = self.read_review(saved)
    current_source = self.read_source(source)

    # Source edits require a new proposal; approval never carries across scope.
    changed = current_source.text != source.text
    logger.info(
        'Review scope checked: title=%r source_changed=%s.',
        item.title,
        changed,
        extra={"details": {'page': item.page_id}},
    )
    if item.human_review != "Rejected" and (changed or (item.status == "Open" and item.human_review == "Revision Requested")):
        logger.info(
            'Revising proposal before further action: title=%r source_changed=%s.',
            item.title,
            changed,
            extra={"details": {'page': item.page_id}},
        )
        proposal = await self.draft(current_source, item)
        item = self.publish_proposal(current_source, proposal, item)
        await self.save_checkpoint(key, current_source, item)
        logger.info(
            'Revision completed; waiting for fresh approval: title=%r.',
            item.title,
            extra={"details": {'page': item.page_id}},
        )
        return item.url

    if item.status == "Open" and item.human_review == "Rejected":
        logger.info(
            'Applying human rejection: title=%r.',
            item.title,
            extra={"details": {'page': item.page_id}},
        )
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
        try:
            decision = await self.decide(request)
            if decision.selected_action_id == "ask_user":
                logger.info(
                    'Execution requires user input; returning to Pending: title=%r.',
                    item.title,
                    extra={"details": {'page': item.page_id}},
                )
                question = decision.clarification_question or decision.suggested_next_step
                self.request_input(source, item, question)
                item = self.read_review(item)
            else:
                result = await self.execute(task, source, decision)
                item = self.save_result(source, item, result)
        except Exception as error:
            # Notion is the human-facing failure surface. A notification failure
            # must not replace the execution exception needed for DBOS recovery.
            try:
                self.save_error(item, f"{type(error).__name__}: {error}")
            except Exception:
                logger.exception("Failed to publish execution error to Workbench: title=%r.", item.title)
            raise
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
    logger.info(
        'Review workflow completed: title=%r status=%s.',
        item.title,
        item.status,
        extra={"details": {'page': item.page_id, 'workflow': DBOS.workflow_id}},
    )
    return item.url


@DBOS.step(name="JobWorkflows.active")
@trace_call("step", "list_active")
def list_active(self: TaskWorkflows) -> list[dict]:
    """Read only managed items waiting for review.

    Returns:
        Local active pointers, excluding legacy Notion records.
    """
    records = self.index.list_active()
    logger.info("Loaded %d managed Open/Executed Workbench items from the local index.", len(records))
    return records


@DBOS.step(name="ProposalWorkflows.read_review")
@trace_call("step", "read_review")
def read_review(self: WorkbenchWorkflows, saved: WorkbenchItem) -> WorkbenchItem:
    """Combine live human fields with the runtime-owned structured payload.

    Args:
        saved: Last verified runtime snapshot.

    Returns:
        Current review state retaining local proposal and result data.
    """
    logger.info(
        'Reading current human review: title=%r.',
        saved.title,
        extra={"details": {'page': saved.page_id}},
    )
    current = self.services.workbench.read_item(saved.page_id)
    current.proposal = saved.proposal
    current.result = saved.result
    current.curation = saved.curation
    current.source_kind = saved.source_kind
    logger.info(
        'Human review read: title=%r status=%s approval=%s acceptance=%s.',
        current.title,
        current.status,
        current.human_review,
        current.result_review,
        extra={"details": {'page': current.page_id}},
    )
    return current


@DBOS.step(name="ProposalWorkflows.route")
@trace_call("step", "route")
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
@trace_call("step", "decide")
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
@trace_call("step", "execute")
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
    logger.info(
        'Executing approved task: title=%r task=%r action=%s redo=%s.',
        task.proposal.title,
        task.proposal.action[:180],
        action,
        task.redo,
        extra={"details": {'workbench': task.workbench_url}},
    )
    if action == "investigate_question":
        logger.info("Dispatching approved action: title=%r capability=investigator action=%s.", task.proposal.title, action)
        request = InvestigationRequest(question=task.proposal.action, context=[source.text, task.instruction])
        report = await self.services.investigator.investigate(request)
        sections = [report.answer]
        sections.extend(f"- [{e.title}]({e.url}): {e.finding}" for e in report.sources)
        sections.extend(report.limitations)
        result = TaskResult(content="\n\n".join(sections), process=report.process)
    elif action in {"complete_task", "organize_material"}:
        logger.info("Dispatching approved action: title=%r capability=task_worker action=%s.", task.proposal.title, action)
        task.instruction += f"\n\nOriginal material:\n{source.text}"
        result = await self.services.worker.execute(task)
    else:
        raise ValueError(f"Unsupported executable action: {action}")
    result.action_id = action
    logger.info(
        'Task execution completed: title=%r action=%s result_characters=%d.',
        task.proposal.title,
        action,
        len(result.content),
        extra={"details": {'workbench': task.workbench_url}},
    )
    return result


@DBOS.step(name="ProposalWorkflows.save_error")
@trace_call("step", "save_error")
def save_error(self: WorkbenchWorkflows, item: WorkbenchItem, error: str) -> None:
    """Publish a short failure diagnosis without changing human approval.

    Args:
        item: Workbench entry whose execution or result publication failed.
        error: Original exception type and message.
    """
    self.services.workbench.save_error(item, error)


@DBOS.step(name="ProposalWorkflows.save_result")
@trace_call("step", "save_result")
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
    expected_key = result_publication_key(item.proposal.version, result.content)
    if current.publication_key == expected_key and current.status == "Executed" and current.result_review != "Unqualified":
        # Recover a completed write without resetting a subsequent human review.
        self.services.workbench.save_result(item, result)
        current.proposal = item.proposal
        current.source_kind = item.source_kind
        current.result = result
        logger.info(
            'Recovered verified execution result: title=%r status=%s; no model rerun required.',
            item.title,
            current.status,
            extra={"details": {'page': item.page_id}},
        )
        return current
    self.check_authorization(source, item)
    self.services.workbench.save_result(item, result)
    current = self.services.workbench.read_item(item.page_id)
    if current.status != "Executed":
        raise RuntimeError(f"Execution result did not reach Executed: {current.status}")
    current.proposal = item.proposal
    current.source_kind = item.source_kind
    current.result = result
    logger.info(
        'Execution result publication verified: title=%r status=%s.',
        current.title,
        current.status,
        extra={"details": {'page': current.page_id}},
    )
    return current


@DBOS.step(name="ProposalWorkflows.request_input")
@trace_call("step", "request_input")
def request_input(self: WorkbenchWorkflows, source: SourceMaterial, item: WorkbenchItem, question: str) -> None:
    """Publish a clarification only while its authorization remains current.

    Args:
        source: Original input scope.
        item: Approved proposal awaiting necessary personal information.
        question: Focused user-owned choice or missing material.
    """
    logger.info(
        'Publishing clarification request: title=%r question_characters=%d.',
        item.title,
        len(question),
        extra={"details": {'page': item.page_id}},
    )
    current = self.services.workbench.read_item(item.page_id)
    expected_key = "clarification:" + digest(question)
    if current.publication_key == expected_key and current.publication_applied:
        self.services.workbench.request_input(item, question)
        return
    self.check_authorization(source, item)
    self.services.workbench.request_input(item, question)


@DBOS.step(name="ProposalWorkflows.extract")
@trace_call("step", "extract")
async def extract(self: WorkbenchWorkflows, item: WorkbenchItem) -> CurationDecision:
    """Checkpoint grounded extraction before archive writes.

    Args:
        item: Human-accepted result.

    Returns:
        Current extraction decision.
    """
    logger.info(
        'Curating accepted result: title=%r.',
        item.title,
        extra={"details": {'page': item.page_id}},
    )
    decision = await self.services.curator.extract(item)
    logger.info(
        'Curation completed: title=%r retained_artifacts=%d.',
        item.title,
        len(decision.artifacts),
        extra={"details": {'page': item.page_id}},
    )
    return decision


@DBOS.step(name="ProposalWorkflows.publish_artifact")
@trace_call("step", "publish_artifact")
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
    logger.info(
        'Publishing retained artifact: destination=%s title=%r.',
        artifact.kind,
        artifact.title[:120],
        extra={"details": {'workbench_page': item.page_id}},
    )
    receipt = self.services.archive.publish(item, artifact, key)
    logger.info(
        'Retained artifact verified.',
        extra={"details": {'workbench_page': item.page_id, 'url': receipt.url}},
    )
    return receipt


@DBOS.step(name="ProposalWorkflows.close_item")
@trace_call("step", "close_item")
def close_item(self: WorkbenchWorkflows, source: SourceMaterial, item: WorkbenchItem, status: str) -> None:
    """Verify current review before applying a terminal visible status.

    Args:
        source: Original source version.
        item: Last human decision snapshot.
        status: Deprecated, Finished, or Archived.
    """
    current = self.services.workbench.read_item(item.page_id)
    if current.status == status:
        logger.info(
            'Terminal status already applied: title=%r status=%s.',
            item.title,
            status,
            extra={"details": {'page': item.page_id}},
        )
        return
    self.check_authorization(source, item)
    self.services.workbench.set_status(item, status)
    logger.info(
        'Workbench finalized: title=%r status=%s.',
        item.title,
        status,
        extra={"details": {'page': item.page_id}},
    )


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
@trace_call("workflow", "process_followups")
async def process_followups(self: RecommendationWorkflows) -> list[str]:
    """Turn Interested reviews into Inbox entries with checkpointed writes.

    Returns:
        Verified newly handled Inbox links.
    """
    urls = []
    records = self.list_interested()
    for position, record in enumerate(records, start=1):
        logger.info(
            'Interested entry %d/%d.',
            position,
            len(records),
            extra={"details": {'feed_page': record['id']}},
        )
        url = self.create_follow_up(record["id"])
        if url:
            urls.append(url)
    await DBOS.set_event_async("followups", urls)
    logger.info("Interested follow-ups completed: inspected=%d verified_or_reused=%d skipped=%d.",
                len(records), len(urls), len(records) - len(urls))
    return urls


@DBOS.step(name="ResearchWorkflows.list_interested")
@trace_call("step", "list_interested")
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
@trace_call("step", "create_follow_up")
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
        logger.info(
            'Skipping already handled Interested entry.',
            extra={"details": {'feed_page': feed_page_id}},
        )
        return ""
    url = self.services.feed.create_follow_up(feed_page_id)
    if url:
        self.index.save(key, feed_page_id, DBOS.workflow_id, url, "Handled")
        logger.info(
            'Interested follow-up verified.',
            extra={"details": {'feed_page': feed_page_id, 'inbox': url}},
        )
    else:
        logger.info(
            'Interested entry required no new follow-up; withdrawn or already submitted.',
            extra={"details": {'feed_page': feed_page_id}},
        )
    return url
