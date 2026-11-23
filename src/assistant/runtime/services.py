"""Bind module-first plugin implementations lazily while exposing application interfaces."""

from functools import cached_property
from pathlib import Path

from assistant.config import AssistantConfig
from plugins import get_plugin

from assistant.components.coordination.brainstorm.protocol import BrainstormProtocol, ResearchLibraryProtocol
from assistant.components.coordination.curator.protocol import CuratorProtocol
from assistant.components.coordination.memory_reviewer.protocol import MemoryReviewerProtocol
from assistant.components.coordination.organizer.protocol import OrganizerProtocol
from assistant.components.coordination.proposer.protocol import ProposerProtocol
from assistant.components.coordination.reconciler.protocol import ReconcilerProtocol
from assistant.components.coordination.router.protocol import RouterProtocol

from assistant.components.execution.writer.protocol import WriterProtocol
from assistant.components.execution.briefer.protocol import BriefWriterProtocol
from assistant.components.execution.investigator.protocol import InvestigatorProtocol
from assistant.components.execution.planner.protocol import PlannerProtocol
from assistant.components.execution.task_worker.protocol import TaskWorkerProtocol

from assistant.components.recommendations.discovery.protocol import DiscoveryProtocol
from assistant.components.recommendations.evidence_reader.protocol import EvidenceReaderProtocol
from assistant.components.recommendations.recommender.protocol import RecommenderProtocol

from assistant.components.data.discovery_pool.protocol import DiscoveryPoolProtocol
from assistant.components.data.memory.protocol import MemoryProtocol
from assistant.components.data.publisher.protocol import PublisherProtocol
from assistant.components.data.research_feed.protocol import ResearchFeedProtocol
from assistant.components.data.sources.models import SourceKind
from assistant.components.data.sources.protocol import SourceProcessor
from assistant.components.data.workbench.protocol import WorkbenchProtocol


class Services:
    """Construct only capabilities used by the selected workflow.

    Attributes:
        config: Provider selections and opaque provider options.
    """

    def __init__(self, config: AssistantConfig) -> None:
        """Keep configuration without initializing models or network clients.

        Args:
            config: Application settings loaded from YAML.
        """
        self.config = config
        self._processors: dict[str, SourceProcessor] = {}

    # Data access and destinations.

    @cached_property
    def memory(self) -> MemoryProtocol:
        """Bind the configured store to this assistant's runtime directory."""
        plugin = get_plugin("data.memory", self.config.providers.memory)
        return plugin.Memory(Path(self.config.runtime.directory).resolve() / "v2" / "memory")

    @cached_property
    def memory_reviewer(self) -> MemoryReviewerProtocol:
        plugin = get_plugin("coordination.memory_reviewer", "local")
        return plugin.MemoryReviewer(self.config.provider_options["local"])

    def processor(self, kind: SourceKind) -> SourceProcessor:
        """Resolve the adapter owning one source collection.

        Args:
            kind: Registered input role, independent of its storage provider.

        Returns:
            Lazy processor exposing the shared source contract.
        """
        if kind == "brainstorm" and kind not in self._processors:
            from plugins.data.sources.brainstorm import BrainstormProcessor
            path = Path(self.config.runtime.directory).resolve() / "v2" / "brainstorm.sqlite"
            self._processors[kind] = BrainstormProcessor(path, limit=self.config.runtime.batch_size)
        if kind not in self._processors:
            name = self.config.providers.processors
            plugin = get_plugin("data.sources", name)
            classes = {"inbox": "InboxProcessor", "todo": "TodoProcessor",
                       "notero": "NoteroProcessor", "simpread": "SimpReadProcessor",
                       "paper": "PaperProcessor", "feed": "FeedProcessor", "pool": "PoolProcessor", "interest": "InterestProcessor"}
            options = dict(self.config.provider_options[name])
            if kind == "pool":
                options["discovery_pool_data_source_id"] = self.discovery_pool.data_source_id()
            options["input_limit"] = self.config.runtime.batch_size
            self._processors[kind] = getattr(plugin, classes[kind])(options)
        return self._processors[kind]

    @cached_property
    def workspace(self):
        """Shared read-only catalog for agents making workspace-dependent decisions."""
        from plugins.data.workspace.notion import Workspace
        return Workspace(self.config.provider_options["notion"])

    @cached_property
    def workbench(self) -> WorkbenchProtocol:
        """Provide human review and report storage."""
        name = self.config.providers.workbench
        plugin = get_plugin("data.workbench", name)
        service = plugin.Workbench(self.config.provider_options[name])
        return service

    @cached_property
    def publisher(self) -> PublisherProtocol:
        """Publish accepted typed outcomes to their destination collections."""
        name = self.config.providers.publisher
        return get_plugin("data.publisher", name).InformationPublisher(self.config.provider_options[name])

    @cached_property
    def feed(self) -> ResearchFeedProtocol:
        """Provide recommendation preferences and autonomous Feed publication."""
        name = self.config.providers.feed
        plugin = get_plugin("data.research_feed", name)
        service = plugin.ResearchFeed(self.config.provider_options[name])
        return service

    @cached_property
    def discovery_pool(self) -> DiscoveryPoolProtocol:
        """Provide the visible discovery cache independently from Feed storage."""
        plugin = get_plugin("data.discovery_pool", self.config.providers.discovery_pool)
        return plugin.DiscoveryPool(self.config.provider_options[self.config.providers.discovery_pool])

    @cached_property
    def recommendation_tags(self):
        """Share a single catalog across Pool, Feed and Papers."""
        name = self.config.providers.discovery_pool
        plugin = get_plugin("data.recommendation_tags", name)
        return plugin.RecommendationTags(self.config.provider_options[name])

    @cached_property
    def research_library(self) -> ResearchLibraryProtocol:
        """Read the research seed and a bounded selection of related knowledge."""
        plugin = get_plugin("coordination.brainstorm", "notion")
        return plugin.ResearchLibrary(self.config.provider_options["notion"],
                                      cursor_path=Path(self.config.runtime.directory).resolve() / "v2" / "brainstorm.sqlite")

    @cached_property
    def brainstorm(self) -> BrainstormProtocol:
        """Explore private research context and public evidence with Codex."""
        name = self.config.providers.brainstorm
        plugin = get_plugin("coordination.brainstorm", name)
        return plugin.Brainstorm(self.config.provider_options.get(name, {}))

    # Coordination roles.

    @cached_property
    def organizer(self) -> OrganizerProtocol:
        """Provide shared source interpretation without publication effects."""
        name = self.config.providers.organizer
        return get_plugin("coordination.organizer", name).InformationOrganizer(self.config.provider_options[name])

    @cached_property
    def proposer(self) -> ProposerProtocol:
        """Provide item-level proposal drafting."""
        name = self.config.providers.proposer
        plugin = get_plugin("coordination.proposer", name)
        service = plugin.Proposer(self.config.provider_options[name], workspace=self.workspace)
        return service

    @cached_property
    def router(self) -> RouterProtocol:
        """Provide executable action selection."""
        name = self.config.providers.router
        plugin = get_plugin("coordination.router", name)
        service = plugin.DecisionRouter(self.config.provider_options[name])
        return service

    @cached_property
    def reconciler(self) -> ReconcilerProtocol:
        """Provide deterministic human-feedback reconciliation, without a model."""
        name = self.config.providers.reconciler
        return get_plugin("coordination.reconciler", name).TaskReconciler()

    @cached_property
    def curator(self) -> CuratorProtocol:
        """Provide extraction without controlling workflow progression."""
        name = self.config.providers.curator
        plugin = get_plugin("coordination.curator", name)
        service = plugin.Curator(self.config.provider_options[name], workspace=self.workspace)
        return service

    # Delegated execution capabilities.

    @cached_property
    def planner(self) -> PlannerProtocol:
        """Provide tool-free planning as a separately approved capability."""
        name = self.config.providers.planner
        return get_plugin("execution.planner", name).Planner(self.config.provider_options[name])

    @cached_property
    def worker(self) -> TaskWorkerProtocol:
        """Provide approved supplied-material task completion."""
        name = self.config.providers.worker
        plugin = get_plugin("execution.task_worker", name)
        service = plugin.TaskWorker(self.config.provider_options[name])
        return service

    @cached_property
    def direct_answer(self) -> TaskWorkerProtocol:
        """Answer an approved question through Codex."""
        from plugins.execution.task_worker.direct_answer import DirectAnswerWorker
        return DirectAnswerWorker(self.config.provider_options.get("codex", {}))

    @cached_property
    def experiment(self) -> TaskWorkerProtocol:
        """Delegate qualified experiments to the native Codex CLI in a persistent workspace."""
        from plugins.execution.task_worker.codex import ExperimentWorker
        return ExperimentWorker(self.config.provider_options.get("codex", {}),
                                Path(self.config.runtime.directory).resolve() / "v2" / "experiments")

    @cached_property
    def investigator(self) -> InvestigatorProtocol:
        """Provide public-source investigation through a replaceable plugin."""
        name = self.config.providers.investigator
        plugin = get_plugin("execution.investigator", name)
        service = plugin.Investigator(self.config.provider_options.get(name, {}))
        return service

    @property
    def aminer_api_key(self) -> str:
        from plugins._shared.aminer import configured_key
        return configured_key(self.config.provider_options.get("aminer", {}))

    @cached_property
    def literature_investigator(self) -> InvestigatorProtocol:
        plugin = get_plugin("execution.investigator", "aminer")
        return plugin.Investigator(self.config.provider_options.get("aminer", {}))

    @cached_property
    def writer(self) -> WriterProtocol:
        """Author all durable output using the configured writing model."""
        name = self.config.providers.writer or self.config.providers.briefs
        return get_plugin("execution.writer", name).Writer(self.config.provider_options[name])

    @cached_property
    def briefs(self) -> BriefWriterProtocol:
        """Provide grounded capture organization."""
        name = self.config.providers.briefs
        plugin = get_plugin("execution.briefer", name)
        service = plugin.Briefer(self.config.provider_options[name])
        return service

    @cached_property
    def direction_proposer(self) -> TaskWorkerProtocol:
        """Develop directions as approved execution, not autonomous interest edits."""
        name = self.config.providers.direction_proposer
        return get_plugin("execution.direction_proposer", name).DirectionProposer(self.config.provider_options[name])

    # Autonomous newspaper capabilities.

    def collector(self, mode: str):
        """Select the weekly agent or lightweight daily source-tool implementation."""
        policy = self.config.runtime.recommendations.collector
        name = policy.deep_provider if mode == "deep" else policy.light_provider
        plugin = get_plugin("recommendations.collector", name)
        options = self.config.provider_options.get(name, {})
        openreview = self.config.provider_options.get("openreview", {})
        if name == "local":
            return plugin.Collector(options, openreview, aminer_api_key=self.aminer_api_key)
        return plugin.Collector(options, openreview)

    @cached_property
    def openreview(self):
        """Retrieve separately attributed public discussions without a model call."""
        from plugins.recommendations.sources.openreview import OpenReviewSource
        return OpenReviewSource(self.config.provider_options.get("openreview", {}))

    @cached_property
    def discovery(self) -> DiscoveryProtocol:
        """Provide date-aware public candidate search or explicit offline fixtures."""
        name = self.config.providers.discovery
        plugin = get_plugin("recommendations.discovery", name)
        service = plugin.Discovery() if name == "demo" else plugin.Discovery(self.config.provider_options[name])
        return service

    @cached_property
    def evidence(self) -> EvidenceReaderProtocol:
        """Provide the material actually read for a candidate."""
        name = self.config.providers.evidence
        plugin = get_plugin("recommendations.evidence_reader", name)
        service = plugin.EvidenceReader() if name == "demo" else plugin.EvidenceReader(self.config.provider_options[name])
        return service

    @cached_property
    def recommender(self) -> RecommenderProtocol:
        """Provide evidence-grounded recommendation assessment."""
        name = self.config.providers.recommender
        plugin = get_plugin("recommendations.recommender", name)
        if name == "demo":
            service = plugin.Recommender()
        else:
            service = plugin.Recommender(self.config.provider_options[name])
        return service

    @cached_property
    def fixture_recommender(self) -> RecommenderProtocol:
        """Provide fixed assessment for explicitly synthetic evidence."""
        plugin = get_plugin("recommendations.recommender", "demo")
        service = plugin.Recommender()
        return service
