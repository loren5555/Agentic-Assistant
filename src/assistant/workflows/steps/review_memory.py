"""Learn role preferences from submitted Workbench comments.

Workbench queues one independent review per human decision with written feedback.
The writer reviews both role notes with project instructions. DBOS retains its reason
and the source page; the file provider commits just the affected role texts.
"""
from dbos import DBOS, SetWorkflowAttributes, SetWorkflowID
from assistant.components.data.memory.models import ReviewFeedback, ROLES
from assistant.components.data.workbench.models import SUBMIT_EXTERNAL_RESULT
from assistant.runtime.agent_context import load_instructions
from logger import get_logger, trace_call

MEMORY_QUEUE = "assistant-memory"
logger = get_logger("workflows.review_memory")


def feedback_events(item, source=None):
    """Capture submitted comments with the actual task, separating the two review stages."""
    proposal = item.proposal
    scope = (proposal.action or proposal.understanding) if proposal else ""
    if source is not None:
        scope = f"Source: {source.text[:2000]}\nProposed action: {scope}"
    version = item.proposal_version or (proposal.version if proposal else 1)
    fields = dict(page_id=item.page_id, page=item.url, version=version, title=item.title, source_kind=item.source_kind or "")
    if item.human_review in {"Approved", "Rejected", "Revision Requested", SUBMIT_EXTERNAL_RESULT} and item.human_instruction.strip():
        yield ReviewFeedback(**fields, stage="proposal", decision=item.human_review,
                             comment=item.human_instruction.strip(), context=scope)
    if item.result_review in {"Qualified", "Unqualified"} and item.result_feedback.strip():
        result = item.result.content if item.result else ""
        yield ReviewFeedback(**fields, stage="result", decision=item.result_review,
                             comment=item.result_feedback.strip(), context=f"{scope}\n{result[:4000]}")


async def queue_feedback(workflows, item, source):
    for event in feedback_events(item, source):
        with SetWorkflowID("memory:" + event.event_id), SetWorkflowAttributes({"title": f"复盘反馈 · {event.title}"}):
            await DBOS.enqueue_workflow_async(MEMORY_QUEUE, workflows.review_memory, event)


@DBOS.workflow(name="ProposalWorkflows.review_memory")
@trace_call("workflow", "review_memory")
async def review_memory(self, event: ReviewFeedback):
    logger.info("Reviewing human feedback: title=%r decision=%s.", event.title, event.decision)
    earlier, instructions = self.memory_evidence(event)
    changed_roles = set()
    for _ in range(3):
        notes = self.read_role_notes()
        revision = await self.revise_notes(event, earlier, notes, instructions)
        updated, conflict = self.apply_notes(event, notes, revision)
        changed_roles.update(updated)
        if not conflict:
            updated = sorted(changed_roles)
            logger.info("Feedback reviewed: title=%r updated=%s reason=%s.",
                        event.title, ", ".join(updated) or "none", revision.reason)
            return {"title": event.title, "url": event.page, "reason": revision.reason, "roles": updated}
    raise RuntimeError("Role notes changed during three successive review attempts")


@DBOS.step(name="ProposalWorkflows.memory_evidence")
def memory_evidence(self, event):
    return self.index.remember_feedback(event), load_instructions("revise-role-memory")


@DBOS.step(name="ProposalWorkflows.read_role_notes")
def read_role_notes(self):
    return [self.services.memory.recall(role) for role in ROLES]


@DBOS.step(name="ProposalWorkflows.revise_notes", retries_allowed=True, max_attempts=3, interval_seconds=2)
@trace_call("step", "revise_notes")
async def revise_notes(self, event, earlier, notes, instructions):
    return await self.services.memory_reviewer.review(event, earlier, notes, instructions)


@DBOS.step(name="ProposalWorkflows.apply_notes")
@trace_call("step", "apply_notes")
def apply_notes(self, event, notes, revision):
    updated = []
    for note in notes:
        replacement = getattr(revision, note.role)
        if replacement is None or replacement.strip() == note.content:
            continue
        if not self.services.memory.apply(note, replacement, event.event_id):
            return updated, True
        updated.append(note.role)
    return updated, False
