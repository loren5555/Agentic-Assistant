"""Share source selection, briefing, publication, and acknowledgement for captures.

Input origin:
    papers supplies kind=notero and articles supplies
    kind=simpread, with an optional raw page ID. CaptureSource reads the raw
    Notion collection; local index entries supply processed versions and cursors.

Output destination:
    RawCapture goes to the briefing capability. CapturePublisher writes a brief
    to Papers/Knowledge, or submit_proposal sends further work to Workbench.
    Confirmed links return to the parent paper/article task. DBOS and the local
    index receive checkpoints; SimpRead alone receives raw-source acknowledgement.

Inputs:
    Notero/SimpRead collection and optional explicit page ID. Batches use pending
    revision selection; each RawCapture includes the content and provenance the
    briefing agent is actually permitted to interpret.

Outputs:
    Confirmed output/proposal URLs, per-capture DBOS checkpoints, handled source
    versions in the local index, and pagination progress after a successful pass.

Workflow:
    Read captures -> compare meaningful fingerprints -> reuse or start one durable
    item operation -> checkpoint the model brief -> publish Papers/Knowledge or
    invoke shared submit_proposal -> save the capture checkpoint -> acknowledge
    the source -> advance the collection cursor after the batch completes.
    Publication rereads source content to reject a changed briefing scope.

Participants and effects:
    papers and articles tasks, capture reader, briefing agent,
    content publisher, and optional proposal drafter/Workbench publisher. Item
    operation identities isolate retries and preserve completed model work.

Boundaries:
    Only SimpRead acknowledgement writes the raw collection; Notero stays
    unchanged except for the publisher-owned Papers flag. A proposal awaits approval.
    These shared operations are bound to TaskWorkflows by runtime/application.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import json

from dbos import DBOS

from assistant.components.captures.models import CaptureBatch, CaptureBrief, CaptureKind, CaptureReceipt, RawCapture
from assistant.components.workbench.models import WorkbenchItem
from assistant.runtime.records import digest, capture_material
from assistant.runtime.recovery import invoke
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows

logger = get_logger("assistant.workflows.steps.organize_capture")


@DBOS.workflow(name="JobWorkflows.captures")
@trace_call("workflow", "organize_captures")
async def organize_captures(self: TaskWorkflows, kind: CaptureKind, page_id: str | None = None) -> list[str]:
    """Scan bounded raw inputs or explicitly reprocess one source.

    Args:
        kind: Notero or SimpRead collection.
        page_id: Optional explicit raw page identity, including archived articles.

    Returns:
        Verified destination URLs.
    """
    if page_id is None:
        batch = self.read_capture_batch(kind)
        captures = batch.captures
    else:
        captures = [self.read_capture(page_id, kind)]
    urls = []
    skipped = 0
    for position, capture in enumerate(captures, start=1):
        logger.debug(
            'Capture item %d/%d: source=%s title=%r.',
            position,
            len(captures),
            capture.kind,
            capture.title[:120],
            extra={"details": {'page': capture.page_id}},
        )
        previous = self.lookup("capture:" + capture.identity)
        if previous is not None and previous["fingerprint"] == capture.fingerprint:
            skipped += 1
            logger.debug(
                'kind=checkpoint Skipping unchanged capture.',
                extra={"details": {'page': capture.page_id, 'existing_output': previous['page_id']}},
            )
            self.acknowledge_capture(capture)
            continue
        operation = "capture:" + digest(capture.identity + capture.fingerprint)
        url = await invoke(operation, self.capture_item, capture)
        urls.append(url)
        logger.info(
            'Capture item resolved.',
            extra={"details": {'page': capture.page_id, 'output': url}},
        )
    if page_id is None:
        self.save_cursor(kind, batch.next_cursor)
    logger.info("Capture pass completed: source=%s read=%d processed_or_reused=%d unchanged=%d explicit_page=%s.",
                kind, len(captures), len(urls), skipped, page_id is not None)
    return urls


@DBOS.workflow(name="JobWorkflows.capture_item")
@trace_call("workflow", "capture_item")
async def capture_item(self: TaskWorkflows, capture: RawCapture) -> str:
    """Organize one raw record or submit it for approval.

    Args:
        capture: Raw source snapshot.

    Returns:
        Verified organized-output or proposal URL.
    """
    brief = await self.brief(capture)
    logger.info(
        'Capture disposition: destination=%s evidence=%s.',
        brief.destination,
        brief.evidence_level,
        extra={"details": {'page': capture.page_id}},
    )
    if brief.destination == "proposal":
        source = capture_material(capture)
        key = f"proposal:{capture.kind}:{capture.page_id}"
        _, state = await self.load_previous(key)
        previous = WorkbenchItem.model_validate(state["item"]) if state else None
        operation = "intake:" + digest(key + source.text)
        url = await invoke(operation, self.proposals.submit_proposal, key, source, previous)
    else:
        receipt = self.publish_capture(capture, brief)
        url = receipt.url
    await self.save_capture_checkpoint(capture, url)
    self.acknowledge_capture(capture)
    return url


@DBOS.step(name="JobWorkflows.capture_batch")
@trace_call("step", "read_capture_batch")
def read_capture_batch(self: TaskWorkflows, kind: CaptureKind) -> CaptureBatch:
    """Select unhandled source versions before downloading their bodies.

    Args:
        kind: Notero or SimpRead collection.

    Returns:
        Captures and their next continuation token.
    """
    # SimpRead's eligible set shrinks on acknowledgement; start at its head
    # rather than continuing a cursor over records removed by our own writes.
    cursor = self.index.cursor(kind) if kind == "notero" else None
    handled_revisions = self.index.capture_revisions(kind)
    logger.info("Reading capture batch: source=%s known_handled_versions=%d limit=%d continuing=%s.",
                kind, len(handled_revisions), self.settings.batch_size, cursor is not None)
    batch = self.services.captures.list_captures(
        kind, self.settings.batch_size, cursor, handled_revisions=handled_revisions,
    )
    logger.info("Capture batch read: source=%s pages=%d has_more=%s.",
                kind, len(batch.captures), batch.next_cursor is not None)
    return batch


@DBOS.step(name="JobWorkflows.read_capture")
@trace_call("step", "read_capture")
def read_capture(self: TaskWorkflows, page_id: str, kind: CaptureKind) -> RawCapture:
    """Read an explicitly selected raw capture.

    Args:
        page_id: Raw Notion page identifier.
        kind: Expected collection.

    Returns:
        Current source material.
    """
    logger.info(
        'Reading explicitly selected capture: source=%s.',
        kind,
        extra={"details": {'page': page_id}},
    )
    capture = self.services.captures.read_capture(page_id, kind)
    return capture


@DBOS.step(name="JobWorkflows.brief")
@trace_call("step", "brief")
async def brief(self: TaskWorkflows, capture: RawCapture) -> CaptureBrief:
    """Checkpoint interpretation before any destination write.

    Args:
        capture: Actual source material.

    Returns:
        Grounded destination classification and brief.
    """
    logger.info(
        'Briefing capture: source=%s title=%r.',
        capture.kind,
        capture.title[:120],
        extra={"details": {'page': capture.page_id}},
    )
    brief = await self.services.briefs.brief(capture)
    logger.info(
        'Brief completed: destination=%s evidence=%s.',
        brief.destination,
        brief.evidence_level,
        extra={"details": {'page': capture.page_id}},
    )
    return brief


@DBOS.step(name="JobWorkflows.publish_capture")
@trace_call("step", "publish_capture")
def publish_capture(self: TaskWorkflows, capture: RawCapture, brief: CaptureBrief) -> CaptureReceipt:
    """Reject changed scope and recover a verified organized write.

    Args:
        capture: Version assessed by the model.
        brief: Cached paper or knowledge brief.

    Returns:
        Verified destination receipt.
    """
    logger.info(
        'Rechecking capture before %s publication.',
        brief.destination,
        extra={"details": {'page': capture.page_id}},
    )
    current = self.services.captures.read_capture(capture.page_id, capture.kind)
    if current.fingerprint != capture.fingerprint:
        raise RuntimeError("Capture changed during briefing; publication stopped")
    receipt = self.services.capture_publisher.publish(capture, brief)
    logger.info(
        'Capture publication verified: destination=%s.',
        brief.destination,
        extra={"details": {'source_page': capture.page_id, 'url': receipt.url}},
    )
    return receipt


@DBOS.step(name="JobWorkflows.capture_checkpoint")
@trace_call("step", "save_capture_checkpoint")
async def save_capture_checkpoint(self: TaskWorkflows, capture: RawCapture, url: str) -> None:
    """Save processed material only after destination verification.

    Args:
        capture: Successfully organized input version.
        url: Verified destination or proposal link.
    """
    await DBOS.set_event_async("capture", {"capture": capture.model_dump(mode="json"), "url": url})
    self.index.save("capture:" + capture.identity, capture.fingerprint, DBOS.workflow_id, url, "Handled")
    logger.debug(
        'Capture state and index saved.',
        extra={"details": {'page': capture.page_id, 'workflow': DBOS.workflow_id}},
    )


@DBOS.step(name="JobWorkflows.acknowledge_capture")
@trace_call("step", "acknowledge_capture")
def acknowledge_capture(self: TaskWorkflows, capture: RawCapture) -> None:
    """Record handled versions; the publisher owns the Notero Papers flag.

    Args:
        capture: Verified source version.
    """
    self.services.captures.mark_handled(capture)
    self.index.save_capture_revision(capture.kind, capture.page_id, capture.revision)
    logger.info(
        'Capture acknowledgement completed: title=%r outcome=%s.',
        capture.title,
        'processed version saved locally' if capture.kind == 'notero' else 'Agent Archived verified; processed version saved locally',
        extra={"details": {'page': capture.page_id}},
    )


@DBOS.step(name="JobWorkflows.save_cursor")
@trace_call("step", "save_cursor")
def save_cursor(self: TaskWorkflows, kind: str, cursor: str | None) -> None:
    """Advance a collection only after all page operations finish.

    Args:
        kind: Raw collection.
        cursor: Next page token, or None after a complete pass.
    """
    self.index.save_cursor(kind, cursor)
    logger.info("Capture cursor saved: source=%s has_more=%s.", kind, cursor is not None)
