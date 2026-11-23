"""Turn a source or an accepted Workbench result into a reader-facing publication.

Curator commissions each work. Writer receives its scope, original evidence, human
instructions and existing destination. Publisher returns a verified archive link.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlsplit
from dbos import DBOS

from assistant.components.coordination.curator.models import RetainedArtifact
from assistant.components.data.sources.models import SourceArchive, SourceMaterial
from assistant.components.data.workbench.models import WorkbenchItem
from assistant.components.execution.briefer.models import PaperReadingMetadata
from assistant.components.recommendations.discovery.models import PaperCandidate
from logger import trace_call


@DBOS.step(name="ProposalWorkflows.commission_source")
@trace_call("step", "commission_source")
async def commission_source(self, source: SourceMaterial):
    return await self.services.curator.commission(source)


async def author(services, source: SourceMaterial, assignment: RetainedArtifact,
                 item: WorkbenchItem | None = None, *, approved: bool = False) -> RetainedArtifact:
    """Read the destination and source evidence before writing or reusing the reviewed body."""
    target = None
    ref = assignment.target_page_id
    if not ref and assignment.kind in {"paper", "knowledge"}:
        ref = await asyncio.to_thread(services.publisher.locate, source, item, assignment)
    if ref:
        target = await asyncio.to_thread(services.workspace.read_for_writing, ref,
                                         assignment.kind)
        assignment = assignment.model_copy(update={
            "target_page_id": target["ref"],
            "target_revision": assignment.target_revision or target["updated"],
        })
    if assignment.target_idea_page_id and not approved:
        target = await asyncio.to_thread(services.workspace.read_for_writing, assignment.target_idea_page_id, "idea")
    if assignment.kind == "paper" and not approved:
        catalog = await asyncio.to_thread(services.recommendation_tags.catalog)
        metadata = {**source.metadata, "Direction catalog": catalog}
        link = getattr(assignment.reading, "paper_url", "") or metadata.get("URL") or metadata.get("Link")
        if (assignment.contribution == "work" and not source.full_text_verified
                and isinstance(link, str) and link.startswith(("https://", "http://"))
                and link in source.context_content and (not item or item.selected_action_id == "organize_material")
                and urlsplit(link).hostname not in {"notion.so", "www.notion.so", "app.notion.com"}):
            evidence = await services.evidence.read(PaperCandidate(id=source.page_id, title=assignment.title, url=link))
            metadata["Primary reading"] = evidence.model_dump(exclude={"process"})
        source = source.model_copy(update={"metadata": metadata})
    manuscript = await services.writer.write(source, assignment, item, target, approved=approved)
    reading = manuscript.reading or assignment.reading
    if assignment.kind == "paper":
        reading = reading or PaperReadingMetadata()
        reading = reading.model_copy(update={"summary": reading.summary or manuscript.summary,
            "paper_url": reading.paper_url or getattr(assignment.reading, "paper_url", ""),
            "directions": reading.directions if reading.directions is not None else getattr(assignment.reading, "directions", None)})
    return assignment.model_copy(update={"content": manuscript.content, "reading": reading,
        "evidence_level": manuscript.evidence_level, "summary": manuscript.summary})


@DBOS.step(name="ProposalWorkflows.write_manuscript")
@trace_call("step", "write_manuscript")
async def write_manuscript(self, source: SourceMaterial, assignment: RetainedArtifact,
                           item: WorkbenchItem | None = None, approved: bool = False):
    return await author(self.services, source, assignment, item, approved=approved)


@DBOS.step(name="ProposalWorkflows.publish_manuscript")
@trace_call("step", "publish_manuscript")
def publish_manuscript(self, source: SourceMaterial, work: RetainedArtifact, key: str) -> SourceArchive:
    if self.read_current_source(source).fingerprint != source.fingerprint:
        raise ValueError(f"Source changed before publication: {source.title}")
    receipt = self.services.publisher.publish(source, None, work, key)
    return SourceArchive(url=receipt.url, destination="papers" if work.kind == "paper" else "knowledge",
                         evidence_level=work.evidence_level, summary=work.summary)
