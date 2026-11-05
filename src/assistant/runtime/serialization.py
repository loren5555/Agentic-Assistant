"""Read existing DBOS snapshots after the component package reorganization.

Input origin:
    DBOS passes its existing base64-encoded Python pickle values.
Output destination:
    Current component models are returned to normal checkpoint/recovery handling.
Responsibility:
    Resolve historical class paths at the serialization boundary. New values use
    current paths and the unchanged py_pickle format. No database rows, workflow
    IDs, schema or version checks are changed here.
"""

import base64
import io
import pickle
from dbos import Serializer

# Persisted values contain model import paths; application imports use only the
# current role-based packages. Keep historical lookup isolated from normal loading.
CLASS_PATHS = {
    'assistant.components.archive.models.ArchiveReceipt': ('assistant.components.data.publisher.models', 'PublicationReceipt'),
    'assistant.components.archive.protocol.ArchiveStoreProtocol': ('assistant.components.data.publisher.protocol', 'ArtifactPublisherProtocol'),
    'assistant.components.captures.models.CaptureBatch': ('assistant.components.execution.briefer.models', 'ReadingBatch'),
    'assistant.components.captures.models.CaptureBrief': ('assistant.components.execution.briefer.models', 'ReadingBrief'),
    'assistant.components.captures.models.CaptureReceipt': ('assistant.components.data.publisher.models', 'BriefPublicationReceipt'),
    'assistant.components.captures.models.PaperReadingMetadata': ('assistant.components.execution.briefer.models', 'PaperReadingMetadata'),
    'assistant.components.captures.models.RawCapture': ('assistant.components.execution.briefer.models', 'ReadingMaterial'),
    'assistant.components.captures.protocol.BriefWriterProtocol': ('assistant.components.execution.briefer.protocol', 'BriefWriterProtocol'),
    'assistant.components.captures.protocol.CapturePublisherProtocol': ('assistant.components.data.publisher.protocol', 'BriefPublisherProtocol'),
    'assistant.components.curator.models.CurationDecision': ('assistant.components.coordination.curator.models', 'CurationDecision'),
    'assistant.components.curator.models.RetainedArtifact': ('assistant.components.coordination.curator.models', 'RetainedArtifact'),
    'assistant.components.curator.protocol.CuratorProtocol': ('assistant.components.coordination.curator.protocol', 'CuratorProtocol'),
    'assistant.components.discovery_pool.models.DiscoveryEntry': ('assistant.components.data.discovery_pool.models', 'DiscoveryEntry'),
    'assistant.components.discovery_pool.protocol.DiscoveryPoolProtocol': ('assistant.components.data.discovery_pool.protocol', 'DiscoveryPoolProtocol'),
    'assistant.components.inputs.models.SourceHistory': ('assistant.components.data.sources.models', 'SourceHistory'),
    'assistant.components.inputs.models.SourceMaterial': ('assistant.components.data.sources.models', 'SourceMaterial'),
    'assistant.components.inputs.protocol.ContextContent': ('assistant.components.data.sources.protocol', 'ContextContent'),
    'assistant.components.investigator.models.InvestigationReport': ('assistant.components.execution.investigator.models', 'InvestigationReport'),
    'assistant.components.investigator.models.InvestigationRequest': ('assistant.components.execution.investigator.models', 'InvestigationRequest'),
    'assistant.components.investigator.models.SourceEvidence': ('assistant.components.execution.investigator.models', 'SourceEvidence'),
    'assistant.components.investigator.protocol.InvestigatorProtocol': ('assistant.components.execution.investigator.protocol', 'InvestigatorProtocol'),
    'assistant.components.organizer.models.OrganizedInformation': ('assistant.components.coordination.organizer.models', 'OrganizedInformation'),
    'assistant.components.organizer.protocol.OrganizerProtocol': ('assistant.components.coordination.organizer.protocol', 'OrganizerProtocol'),
    'assistant.components.planner.models.ExecutionPlan': ('assistant.components.execution.planner.models', 'ExecutionPlan'),
    'assistant.components.planner.models.PlanningResult': ('assistant.components.execution.planner.models', 'PlanningResult'),
    'assistant.components.planner.protocol.PlannerProtocol': ('assistant.components.execution.planner.protocol', 'PlannerProtocol'),
    'assistant.components.processors.protocol.SourceProcessor': ('assistant.components.data.sources.protocol', 'SourceProcessor'),
    'assistant.components.proposer.models.Proposal': ('assistant.components.coordination.proposer.models', 'Proposal'),
    'assistant.components.proposer.protocol.ProposerProtocol': ('assistant.components.coordination.proposer.protocol', 'ProposerProtocol'),
    'assistant.components.publisher.protocol.PublisherProtocol': ('assistant.components.data.publisher.protocol', 'PublisherProtocol'),
    'assistant.components.recommendations.models.DiscoveryResult': ('assistant.components.recommendations.discovery.models', 'DiscoveryResult'),
    'assistant.components.recommendations.models.PaperCandidate': ('assistant.components.recommendations.discovery.models', 'PaperCandidate'),
    'assistant.components.recommendations.models.PaperEvidence': ('assistant.components.recommendations.evidence_reader.models', 'PaperEvidence'),
    'assistant.components.recommendations.models.PoolTranslation': ('assistant.components.recommendations.recommender.models', 'PoolTranslation'),
    'assistant.components.recommendations.models.PoolTranslations': ('assistant.components.recommendations.recommender.models', 'PoolTranslations'),
    'assistant.components.recommendations.models.RankedCandidates': ('assistant.components.recommendations.recommender.models', 'RankedCandidates'),
    'assistant.components.recommendations.models.Recommendation': ('assistant.components.recommendations.recommender.models', 'Recommendation'),
    'assistant.components.recommendations.models.RecommendationAssessment': ('assistant.components.recommendations.recommender.models', 'RecommendationAssessment'),
    'assistant.components.recommendations.models.RecommendationRun': ('assistant.components.recommendations.recommender.models', 'RecommendationRun'),
    'assistant.components.recommendations.models.ResearchInterest': ('assistant.components.recommendations.discovery.models', 'ResearchInterest'),
    'assistant.components.recommendations.models.SourceQuality': ('assistant.components.recommendations.discovery.models', 'SourceQuality'),
    'assistant.components.recommendations.protocol.DiscoveryProtocol': ('assistant.components.recommendations.discovery.protocol', 'DiscoveryProtocol'),
    'assistant.components.recommendations.protocol.EvidenceReaderProtocol': ('assistant.components.recommendations.evidence_reader.protocol', 'EvidenceReaderProtocol'),
    'assistant.components.recommendations.protocol.RecommenderProtocol': ('assistant.components.recommendations.recommender.protocol', 'RecommenderProtocol'),
    'assistant.components.recommendations.protocol.ResearchFeedProtocol': ('assistant.components.data.research_feed.protocol', 'ResearchFeedProtocol'),
    'assistant.components.reconciler.models.Reconciliation': ('assistant.components.coordination.reconciler.models', 'Reconciliation'),
    'assistant.components.reconciler.protocol.ReconcilerProtocol': ('assistant.components.coordination.reconciler.protocol', 'ReconcilerProtocol'),
    'assistant.components.router.models.ActionCandidate': ('assistant.components.coordination.router.models', 'ActionCandidate'),
    'assistant.components.router.models.RouterDecision': ('assistant.components.coordination.router.models', 'RouterDecision'),
    'assistant.components.router.models.RouterInput': ('assistant.components.coordination.router.models', 'RouterInput'),
    'assistant.components.router.protocol.RouterProtocol': ('assistant.components.coordination.router.protocol', 'RouterProtocol'),
    'assistant.components.task_worker.models.TaskRequest': ('assistant.components.execution.task_worker.models', 'TaskRequest'),
    'assistant.components.task_worker.models.TaskResult': ('assistant.components.execution.task_worker.models', 'TaskResult'),
    'assistant.components.task_worker.protocol.TaskWorkerProtocol': ('assistant.components.execution.task_worker.protocol', 'TaskWorkerProtocol'),
    'assistant.components.workbench.models.WorkbenchItem': ('assistant.components.data.workbench.models', 'WorkbenchItem'),
    'assistant.components.workbench.protocol.WorkbenchProtocol': ('assistant.components.data.workbench.protocol', 'WorkbenchProtocol'),
}


class ComponentUnpickler(pickle.Unpickler):
    """Resolve renamed model classes without importing obsolete component trees."""

    def find_class(self, module: str, name: str):
        """Map a stored component class to its current owner, otherwise use pickle."""
        module, name = CLASS_PATHS.get(f"{module}.{name}", (module, name))
        return super().find_class(module, name)


class ComponentSerializer(Serializer):
    """Preserve DBOS's pickle wire format while resolving moved component models."""

    def name(self) -> str:
        """Keep the serialization label used by existing DBOS records."""
        return "py_pickle"

    def serialize(self, data: object) -> str:
        """Write ordinary pickle values using their current Python class paths."""
        return base64.b64encode(pickle.dumps(data)).decode("utf-8")

    def deserialize(self, serialized_data: str) -> object:
        """Read current or historical snapshots without modifying stored bytes."""
        return ComponentUnpickler(io.BytesIO(base64.b64decode(serialized_data))).load()
