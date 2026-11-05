"""Interpret review states independently of workers and storage providers."""

from typing import Protocol
from assistant.components.data.sources.models import SourceMaterial
from assistant.components.data.workbench.models import WorkbenchItem
from assistant.components.coordination.reconciler.models import Reconciliation


class ReconcilerProtocol(Protocol):
    """Turn a feedback snapshot into one idempotent source update."""

    def reconcile(self, source: SourceMaterial, item: WorkbenchItem) -> Reconciliation:
        """Interpret feedback without replanning or executing.

        Args:
            source: Original source scope of the reviewed task.
            item: Current human decision and previous deliverable.

        Returns:
            Source feedback and the old task's terminal status.
        """
        ...
