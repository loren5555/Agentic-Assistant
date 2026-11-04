"""Reuse specialized Notion writers behind one accepted-output boundary."""

from collections.abc import Mapping
from assistant.components.inputs.models import SourceMaterial
from assistant.components.workbench.models import WorkbenchItem
from assistant.components.curator.models import RetainedArtifact
from assistant.components.captures.models import RawCapture, CaptureBrief, PaperReadingMetadata
from assistant.components.archive.models import ArchiveReceipt
from plugins.archive.notion import ArchiveStore
from plugins.captures.notion.publisher import CapturePublisher
from logger import get_logger, trace_call


class InformationPublisher:
    """Choose a destination writer after human acceptance, without new model calls."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Bind writer implementations without network requests.

        Args:
            options: Notion source and output database configuration.
        """
        self.archive = ArchiveStore(options)
        self.papers = CapturePublisher(options)
        self.logger = get_logger("plugins.publisher.notion")

    def initialize_schema(self) -> None:
        """Prepare output keys and reading properties."""
        self.archive.initialize_schema()
        self.papers.initialize_schema()

    @trace_call("component", "publisher.publish")
    def publish(self, source: SourceMaterial, item: WorkbenchItem,
                artifact: RetainedArtifact, key: str) -> ArchiveReceipt:
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
        if artifact.kind == "paper":
            metadata = dict(source.metadata)
            metadata["Source Version"] = source.version
            metadata["Human Supplement"] = source.supplement
            metadata["Source Type"] = {"notero": "Zotero", "simpread": "SimpRead"}.get(source.kind, source.kind.title())
            capture = RawCapture(kind="notero" if source.kind == "notero" else "simpread",
                                 page_id=source.page_id, url=source.url, title=source.title,
                                 text=source.text, metadata=metadata, revision=source.revision,
                                 full_text_verified=source.full_text_verified)
            content = artifact.content + f"\n\nWorkbench: {item.url}"
            brief = CaptureBrief(destination="papers", title=artifact.title, content=content,
                                 reason=artifact.reason, evidence_level="full_text" if source.full_text_verified else "notes",
                                 reading=artifact.reading or PaperReadingMetadata())
            receipt = self.papers.publish(capture, brief)
            result = ArchiveReceipt(key=key, url=receipt.url)
        else:
            result = self.archive.publish(item, artifact, key)
        self.logger.info('Accepted output published: title=%r destination=%s.', artifact.title, artifact.kind)
        return result
