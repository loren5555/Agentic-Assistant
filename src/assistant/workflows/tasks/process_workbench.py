"""Execute approved work and curate accepted results.

Input origin:
    Managed Workbench approvals and accepted results; feedback is collected by
    reconcile-feedback before this workflow selects executable items.
Output destination:
    Execution returns to Workbench. Accepted outcomes pass through Curator and
    Information Publisher to Papers, Knowledge, Ideas or Research Interests.
Responsibility:
    Workers execute one complete snapshot. Revision, rejection and unqualified
    results never invoke a worker directly; source re-entry belongs to Reconciler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import json

from dbos import DBOS

from assistant.components.archive.models import ArchiveReceipt
from assistant.components.curator.models import CurationDecision, RetainedArtifact
from assistant.components.inputs.models import SourceMaterial
from assistant.components.investigator.models import InvestigationRequest
from assistant.components.router.actions import EXECUTION_ACTIONS
from assistant.components.router.models import RouterDecision, RouterInput
from assistant.components.task_worker.models import TaskRequest, TaskResult
from assistant.components.workbench.models import WorkbenchItem, result_publication_key
from assistant.components.captures.models import RawCapture
from assistant.runtime.records import digest
from assistant.runtime.recovery import invoke
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows, WorkbenchWorkflows
    from assistant.workflows.tasks.recommend_papers import RecommendationWorkflows

logger = get_logger("assistant.workflows.tasks.process_workbench")


@DBOS.workflow(name="JobWorkflows.process_workbench.v2")
@trace_call("workflow", "process_workbench")
async def process_workbench(self: TaskWorkflows) -> list[str]:
    """Reconcile feedback, then execute approved work or curate accepted results.

    Returns:
        Workbench links advanced during this pass.
    """
    urls = await self.reconcile_feedback()
    records = self.list_active()
    logger.info('Processing Workbench: active=%d.', len(records))
    for position, record in enumerate(records, 1):
        state = await DBOS.get_event_async(record["workflow_id"], "state", timeout_seconds=0)
        if state is None:
            raise RuntimeError(f"Managed work has no state: {record['workflow_id']}")
        saved = WorkbenchItem.model_validate(state["item"])
        current = self.proposals.read_review(saved)
        logger.info('Review item %d/%d: title=%r status=%s approval=%s acceptance=%s.',
                    position, len(records), current.title, current.status,
                    current.human_review, current.result_review)
        if current.needs_input:
            logger.info('Awaiting human input: title=%r; answer in Human Instruction, then submit Human Review.', current.title)
            continue
        actionable = (
            current.status == "Open" and current.human_review == "Approved"
            or current.status == "Executed" and current.result_review == "Qualified"
        )
        if not actionable:
            logger.info('Waiting for human review: title=%r.', current.title)
            continue
        signal = {"owner": record["workflow_id"], "item": current.model_dump(exclude={"proposal", "result", "curation"})}
        operation = "review:v2:" + digest(json.dumps(signal, sort_keys=True))
        urls.append(await invoke(operation, self.proposals.review_item, record["source_key"], state))
    logger.info('Workbench pass completed: advanced=%d.', len(urls))
    return urls


@DBOS.workflow(name="ProposalWorkflows.review_item.v2")
@trace_call("workflow", "review_item")
async def review_item(self: WorkbenchWorkflows, key: str, state: dict) -> str:
    """Execute one approved snapshot or retain one accepted result.

    Args:
        key: Source identity in the local business index.
        state: Saved source, proposal and any previous result.

    Returns:
        Human-facing Workbench URL.
    """
    source = SourceMaterial.model_validate(state["source"])
    saved = WorkbenchItem.model_validate(state["item"])
    item = self.read_review(saved)
    if item.needs_input:
        logger.info('Clarification proposal awaits feedback reconciliation: title=%r.', item.title)
        return item.url
    current_source = self.read_source(source)
    if current_source.fingerprint != source.fingerprint:
        logger.info('Source changed; returning work to normal intake: title=%r.', item.title)
        return await self.reconcile_item(key, source, item)
    if item.publication_key != saved.publication_key:
        raise RuntimeError("Report publication changed; reconcile the work before execution")

    if item.status == "Open" and item.human_review == "Approved":
        task = TaskRequest(workbench_url=item.url, proposal=item.proposal,
                           instruction=item.human_instruction, source=source)
        try:
            decision = await self.decide(self.route(task, source))
            if decision.selected_action_id == "ask_user":
                question = decision.clarification_question or decision.suggested_next_step
                self.request_input(source, item, question)
                item = self.read_review(item)
            else:
                result = await self.execute(task, source, decision)
                item = self.save_result(source, item, result)
        except Exception as error:
            try:
                self.save_error(item, f"{type(error).__name__}: {error}")
            except Exception:
                logger.exception("Could not report execution error: title=%r.", item.title)
            raise
    elif item.status == "Executed" and item.result_review == "Qualified":
        decision = await self.extract(item)
        for position, artifact in enumerate(decision.artifacts):
            identity = f"{item.page_id}:{item.proposal.version}:{position}:{artifact.model_dump_json()}"
            receipt = self.publish_artifact(source, item, artifact, digest(identity))
            decision.receipts.append(receipt)
        item.curation = decision
        status = "Archived" if decision.artifacts else "Finished"
        self.close_item(source, item, status)
        item.status = status

    await self.save_checkpoint(key, source, item)
    logger.info('Workbench work completed: title=%r status=%s.', item.title, item.status)
    return item.url


@DBOS.step(name="JobWorkflows.active")
@trace_call("step", "list_active")
def list_active(self: TaskWorkflows) -> list[dict]:
    """Read only managed items waiting for review.

    Returns:
        Local active pointers, excluding legacy Notion records.
    """
    records = self.index.list_active()
    logger.info("Loaded %d managed Open/Needs Input/Executed Workbench items from the local index.", len(records))
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
        context=[source.context_content], candidates=EXECUTION_ACTIONS,
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
        'Executing approved task: title=%r task=%r action=%s source_version=%d.',
        task.proposal.title,
        task.proposal.action[:180],
        action,
        source.version,
        extra={"details": {'workbench': task.workbench_url}},
    )
    if action == "investigate_question":
        logger.info("Dispatching approved action: title=%r capability=investigator action=%s.", task.proposal.title, action)
        request = InvestigationRequest(question=task.proposal.action, context=[source.context_content, task.instruction])
        report = await self.services.investigator.investigate(request)
        sections = [report.answer]
        sections.extend(f"- [{e.title}]({e.url}): {e.finding}" for e in report.sources)
        sections.extend(report.limitations)
        result = TaskResult(content="\n\n".join(sections), process=report.process)
    elif action == "organize_material" and source.kind in {"notero", "simpread"}:
        capture = RawCapture(kind=source.kind, page_id=source.page_id, url=source.url,
                             title=source.title, text=source.context_content,
                             metadata=source.metadata, revision=source.revision,
                             full_text_verified=source.full_text_verified)
        brief = await self.services.briefs.brief(capture)
        artifacts = []
        if brief.destination in {"papers", "knowledge"}:
            artifacts.append(RetainedArtifact(kind="paper" if brief.destination == "papers" else "knowledge",
                                              title=brief.title, content=brief.content, reason=brief.reason,
                                              reading=brief.reading))
        result = TaskResult(content=brief.content, artifacts=artifacts)
    elif action == "propose_direction":
        result = await self.services.direction_proposer.execute(task)
    elif action in {"complete_task", "organize_material"}:
        logger.info("Dispatching approved action: title=%r capability=task_worker action=%s.", task.proposal.title, action)
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
    expected_key = result_publication_key(item.proposal.version, result.model_dump_json(exclude={"process", "action_id"}))
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
    else:
        self.check_authorization(source, item)
        self.services.workbench.request_input(item, question)
    item.proposal = item.proposal.model_copy(update={"kind": "clarification", "questions": [question]})


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
    if item.result.artifacts:
        # Structured products were part of the accepted result, not inferred later.
        decision = CurationDecision(reason="Retain the structured outputs accepted by the user.",
                                    artifacts=item.result.artifacts)
    else:
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
    receipt = self.services.publisher.publish(source, item, artifact, key)
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
    if current_source.fingerprint != source.fingerprint or any(getattr(current, field) != getattr(item, field) for field in fields):
        raise RuntimeError("Source, publication, or human authorization changed; publication stopped")
