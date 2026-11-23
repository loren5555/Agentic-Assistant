"""Author the manuscript commissioned by Curator for review or publication."""

from typing import Protocol

from assistant.components.coordination.curator.models import RetainedArtifact
from assistant.components.data.sources.models import SourceMaterial
from assistant.components.data.workbench.models import WorkbenchItem
from assistant.components.execution.writer.models import Manuscript


class WriterProtocol(Protocol):
    async def write(
        self, source: SourceMaterial, assignment: RetainedArtifact, item: WorkbenchItem | None,
        target: dict | None, *, approved: bool = False,
    ) -> Manuscript:
        """Use the reader's task and supplied evidence, preserving an approved manuscript verbatim."""
        ...
