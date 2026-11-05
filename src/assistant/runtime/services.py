"""Bind module-first plugin implementations lazily while exposing application interfaces."""

from functools import cached_property

from assistant.config import AssistantConfig
from plugins import get_plugin

from assistant.components.coordination.curator.protocol import CuratorProtocol
from assistant.components.coordination.organizer.protocol import OrganizerProtocol
from assistant.components.coordination.proposer.protocol import ProposerProtocol
from assistant.components.coordination.reconciler.protocol import ReconcilerProtocol
from assistant.components.coordination.router.protocol import RouterProtocol

from assistant.components.execution.briefer.protocol import BriefWriterProtocol
from assistant.components.execution.investigator.protocol import InvestigatorProtocol
from assistant.components.execution.planner.protocol import PlannerProtocol
from assistant.components.execution.task_worker.protocol import TaskWorkerProtocol

from assistant.components.recommendations.discovery.protocol import DiscoveryProtocol
from assistant.components.recommendations.evidence_reader.protocol import EvidenceReaderProtocol
from assistant.components.recommendations.recommender.protocol import RecommenderProtocol

from assistant.components.data.discovery_pool.protocol import DiscoveryPoolProtocol
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

    def processor(self, kind: SourceKind) -> SourceProcessor:
        """Resolve the adapter owning one source collection.

        Args:
            kind: Registered input role, independent of its storage provider.

        Returns:
            Lazy processor exposing the shared source contract.
        """
        if kind not in self._processors:
            name = self.config.providers.processors
            plugin = get_plugin("data.sources", name)
            classes = {"inbox": "InboxProcessor", "todo": "TodoProcessor",
                       "notero": "NoteroProcessor", "simpread": "SimpReadProcessor",
                       "paper": "PaperProcessor", "feed": "FeedProcessor", "interest": "InterestProcessor"}
            options = dict(self.config.provider_options[name])
            options["input_limit"] = self.config.runtime.batch_size
            self._processors[kind] = getattr(plugin, classes[kind])(options)
        return self._processors[kind]

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
        service = plugin.Proposer(self.config.provider_options[name])
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
        service = plugin.Curator(self.config.provider_options[name])
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
    def investigator(self) -> InvestigatorProtocol:
        """Provide public-source investigation through a replaceable plugin."""
        name = self.config.providers.investigator
        plugin = get_plugin("execution.investigator", name)
        service = plugin.Investigator(self.config.provider_options[name])
        return service

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
