"""Share input submission, not source extraction or downstream execution.

Input origin:
    Source-specific processors selected by propose-tasks, organize-papers,
    organize-articles and process-signals.
Output destination:
    Grounded briefs go to Papers or Knowledge. Follow-up proposals go to Workbench.
Responsibility:
    Deduplicate effective source versions and dispatch one durable intake per item.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from dbos import DBOS
from assistant.components.data.sources.models import SourceMaterial
from assistant.runtime.recovery import invoke
from logger import get_logger, trace_call

if TYPE_CHECKING:
    from assistant.runtime.application import TaskWorkflows

logger = get_logger("workflows.intake_sources")


@DBOS.workflow(name="JobWorkflows.intake_sources.v2")
@trace_call("workflow", "intake_sources")
async def intake_sources(self: TaskWorkflows, kinds: list[str], page_id: str | None = None) -> list[str]:
    """Submit pending source snapshots through the common proposal boundary.

    Args:
        kinds: Source roles belonging to this business workflow.
        page_id: Optional explicit source for a one-source workflow.

    Returns:
        One link per actionable input: the follow-up proposal when present, otherwise its archive.
    """
    urls = []
    for kind in kinds:
        sources = self.read_sources(kind, page_id)
        for position, source in enumerate(sources, 1):
            logger.info('Processing input %d/%d: title=%r source=%s version=%d.',
                        position, len(sources), source.title, kind, source.version)
            key = f"proposal:{kind}:{source.page_id}"
            record = self.lookup(key, source.intake_snapshot)
            if record and source.intake_snapshot == record.get("acknowledged_snapshot"):
                logger.info('Input already acknowledged: title=%r.', source.title)
                continue
            submitted = record["fingerprint"] if record else None
            if submitted and not submitted.startswith("snapshot:"):
                # Older index rows recorded a body hash. Recover their actual
                # submitted timestamp from the saved proposal instead.
                state = await DBOS.get_event_async(record["workflow_id"], "state", timeout_seconds=0)
                submitted = SourceMaterial.model_validate(state["source"]).intake_snapshot if state else None
            if submitted == source.intake_snapshot:
                logger.info('Input already submitted: title=%r; confirming acknowledgement.', source.title)
                state = await DBOS.get_event_async(record["workflow_id"], "state", timeout_seconds=0)
                retained = SourceMaterial.model_validate(state["source"]) if state else source
                self.proposals.acknowledge(retained)
                continue
            operation = "intake:v2:" + source.intake_snapshot
            url = await invoke(operation, self.proposals.submit_proposal, key, source)
            if url:
                urls.append(url)
    logger.info('Intake finished: sources=%s output_links=%d.', ", ".join(kinds), len(urls))
    return urls


@DBOS.step(name="JobWorkflows.read_sources.v2")
@trace_call("step", "read_sources")
def read_sources(self: TaskWorkflows, kind: str, page_id: str | None = None) -> list[SourceMaterial]:
    """Checkpoint one source adapter's bounded query.

    Args:
        kind: Source role with independent extraction rules.
        page_id: Optional specific record.

    Returns:
        Current pending input snapshots.
    """
    return self.services.processor(kind).list_pending(page_id)
