"""Reuse specialized Notion writers behind one accepted-output boundary."""

from collections.abc import Mapping
from assistant.components.data.sources.models import SourceMaterial
from assistant.components.data.workbench.models import WorkbenchItem
from assistant.components.coordination.curator.models import RetainedArtifact
from assistant.components.execution.briefer.models import ReadingMaterial, ReadingBrief, PaperReadingMetadata
from assistant.components.data.publisher.models import BriefPublicationReceipt, PublicationReceipt
from plugins.data.publisher.notion.artifacts import ArtifactPublisher
from plugins.data.publisher.notion.briefs import BriefPublisher
from assistant.components.recommendations.discovery.models import PaperCandidate
from assistant.components.recommendations.discovery.identity import candidate_identity
from logger import get_logger, trace_call


class InformationPublisher:
    """Publish grounded source briefs and accepted task outputs to their destinations."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind writer implementations without network requests.

        Args:
            options: Notion source and output database configuration.
        """
        self.archive = ArtifactPublisher(options)
        self.papers = BriefPublisher(options)
        self.logger = get_logger("plugins.data.publisher.notion")

    def initialize_schema(self) -> None:
        """Prepare output keys and reading properties."""
        self.archive.initialize_schema()
        self.papers.initialize_schema()

    def publish_source_brief(self, material: ReadingMaterial, brief: ReadingBrief) -> BriefPublicationReceipt:
        """Save a grounded source brief before any follow-up proposal."""
        return self.papers.publish(material, brief, mark_notero=False)

    def _material(self, source: SourceMaterial, item: WorkbenchItem | None,
                  artifact: RetainedArtifact) -> tuple[ReadingMaterial, bool]:
        """Carry source bibliography only when the assignment describes that same work."""
        primary = item is None or getattr(item, "selected_action_id", "") == "organize_material"
        paper_url = getattr(artifact.reading, "paper_url", "")
        origin_url = source.metadata.get("URL") or source.metadata.get("Link")
        same_paper = False
        if artifact.kind == "paper":
            same_title = source.title.strip().casefold() == artifact.title.strip().casefold()
            if paper_url and isinstance(origin_url, str) and origin_url:
                paper = PaperCandidate(id="", title=artifact.title, url=paper_url)
                origin = PaperCandidate(id="", title=source.title, url=origin_url)
                same_link = candidate_identity(paper) == candidate_identity(origin)
                same_paper = same_title or same_link
            else:
                same_paper = same_title
            primary = primary and same_paper
        metadata = dict(source.metadata) if primary else {}
        if paper_url.startswith(("https://", "http://")):
            metadata["URL"] = paper_url
        metadata["Source Type"] = {"notero": "Zotero", "simpread": "SimpRead"}.get(source.kind, source.kind.title())
        material = ReadingMaterial(kind=source.kind if source.kind in {"notero", "simpread"} else "inbox",
            page_id=source.page_id, url=source.url, title=source.title if primary else artifact.title,
            text=source.text, metadata=metadata, revision=source.revision,
            full_text_verified=source.full_text_verified and (artifact.kind != "paper" or same_paper))
        return material, primary

    def locate(self, source, item, assignment):
        """Resolve the work through the same identity rules used at publication."""
        material, primary = self._material(source, item, assignment)
        destination = "papers" if assignment.kind == "paper" else "knowledge"
        if not primary and not material.metadata.get("URL"):
            return None
        return self.papers.locate(material, destination, assignment.title, None if primary else "lookup")

    @trace_call("component", "publisher.publish")
    def publish(self, source: SourceMaterial, item: WorkbenchItem | None,
                artifact: RetainedArtifact, key: str) -> PublicationReceipt:
        """Publish one accepted paper, knowledge, idea or interest product.

        Args:
            source: Effective original material and evidence completeness.
            item: Accepted work retaining its human review history.
            artifact: Selected typed output.
            key: Stable publication identity.

        Returns:
            Verified publication receipt.
        """
        self.logger.info('Publishing accepted output: title=%r destination=%s.', artifact.title, artifact.kind)
        if artifact.kind in {"paper", "knowledge"}:
            material, primary = self._material(source, item, artifact)
            content = artifact.content
            if item:
                content += f"\n\n[Workbench]({item.url})"
            brief = ReadingBrief(destination="papers" if artifact.kind == "paper" else "knowledge",
                title=artifact.title, content=content, reason=artifact.reason,
                evidence_level=artifact.evidence_level or "notes", reading=artifact.reading or PaperReadingMetadata())
            receipt = self.papers.publish(material, brief, artifact_key=None if primary else key,
                mark_notero=item is not None and primary, target_page_id=artifact.target_page_id,
                contribution=artifact.contribution, edition=key, target_revision=artifact.target_revision)
            result = PublicationReceipt(key=key, url=receipt.url)
        else:
            if item is None:
                raise ValueError(f"{artifact.kind} requires an accepted Workbench item")
            result = self.archive.publish(item, artifact, key)
        self.logger.info('Accepted output published: title=%r destination=%s.', artifact.title, artifact.kind)
        return result
