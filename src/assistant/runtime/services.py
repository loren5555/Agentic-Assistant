"""Bind module-first plugin implementations lazily while exposing application interfaces."""

from functools import cached_property

from assistant.components.archive.protocol import ArchiveStoreProtocol
from assistant.components.captures.protocol import CapturePublisherProtocol, CaptureSourceProtocol, BriefWriterProtocol
from assistant.components.curator.protocol import CuratorProtocol
from assistant.components.inputs.protocol import InputSourceProtocol
from assistant.components.investigator.protocol import InvestigatorProtocol
from assistant.components.proposer.protocol import ProposerProtocol
from assistant.components.recommendations.protocol import DiscoveryProtocol, EvidenceReaderProtocol, RecommenderProtocol, ResearchFeedProtocol
from assistant.components.router.protocol import RouterProtocol
from assistant.components.task_worker.protocol import TaskWorkerProtocol
from assistant.components.workbench.protocol import WorkbenchProtocol
from assistant.config import AssistantConfig
from plugins import get_plugin


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

    @cached_property
    def inputs(self) -> InputSourceProtocol:
        """Provide input reading and post-publication acknowledgements."""
        name = self.config.providers.inputs
        plugin = get_plugin("inputs", name)
        service = plugin.InputSource(self.config.provider_options[name])
        return service

    @cached_property
    def workbench(self) -> WorkbenchProtocol:
        """Provide human review and report storage."""
        name = self.config.providers.workbench
        plugin = get_plugin("workbench", name)
        service = plugin.Workbench(self.config.provider_options[name])
        return service

    @cached_property
    def proposer(self) -> ProposerProtocol:
        """Provide item-level proposal drafting."""
        name = self.config.providers.proposer
        plugin = get_plugin("proposer", name)
        service = plugin.Proposer(self.config.provider_options[name])
        return service

    @cached_property
    def router(self) -> RouterProtocol:
        """Provide executable action selection."""
        name = self.config.providers.router
        plugin = get_plugin("router", name)
        service = plugin.DecisionRouter(self.config.provider_options[name])
        return service

    @cached_property
    def worker(self) -> TaskWorkerProtocol:
        """Provide approved supplied-material task completion."""
        name = self.config.providers.worker
        plugin = get_plugin("task_worker", name)
        service = plugin.TaskWorker(self.config.provider_options[name])
        return service

    @cached_property
    def investigator(self) -> InvestigatorProtocol:
        """Provide public-source investigation through a replaceable plugin."""
        name = self.config.providers.investigator
        plugin = get_plugin("investigator", name)
        service = plugin.Investigator(self.config.provider_options[name])
        return service

    @cached_property
    def archive(self) -> ArchiveStoreProtocol:
        """Provide verified Knowledge and Ideas publication."""
        name = self.config.providers.archive
        plugin = get_plugin("archive", name)
        service = plugin.ArchiveStore(self.config.provider_options[name])
        return service

    @cached_property
    def curator(self) -> CuratorProtocol:
        """Provide extraction without controlling workflow progression."""
        name = self.config.providers.curator
        plugin = get_plugin("curator", name)
        service = plugin.Curator(self.config.provider_options[name])
        return service

    @cached_property
    def captures(self) -> CaptureSourceProtocol:
        """Provide bounded reads of independent raw Notero and SimpRead inputs."""
        name = self.config.providers.captures
        plugin = get_plugin("captures", name)
        service = plugin.CaptureSource(self.config.provider_options[name])
        return service

    @cached_property
    def briefs(self) -> BriefWriterProtocol:
        """Provide grounded capture organization."""
        name = self.config.providers.briefs
        plugin = get_plugin("captures", name)
        service = plugin.CaptureBriefer(self.config.provider_options[name])
        return service

    @cached_property
    def capture_publisher(self) -> CapturePublisherProtocol:
        """Provide organized Papers and Knowledge publication."""
        name = self.config.providers.captures
        plugin = get_plugin("captures", name)
        service = plugin.CapturePublisher(self.config.provider_options[name])
        return service

    @cached_property
    def feed(self) -> ResearchFeedProtocol:
        """Provide research interests, recommendations, and Interested follow-ups."""
        name = self.config.providers.feed
        plugin = get_plugin("recommendations", name)
        service = plugin.ResearchFeed(self.config.provider_options[name])
        return service

    @cached_property
    def discovery(self) -> DiscoveryProtocol:
        """Provide candidate discovery; the initial implementation is demo-only."""
        plugin = get_plugin("recommendations", self.config.providers.discovery)
        service = plugin.Discovery()
        return service

    @cached_property
    def evidence(self) -> EvidenceReaderProtocol:
        """Provide the material actually read for a candidate."""
        plugin = get_plugin("recommendations", self.config.providers.evidence)
        service = plugin.EvidenceReader()
        return service

    @cached_property
    def recommender(self) -> RecommenderProtocol:
        """Provide evidence-grounded recommendation assessment."""
        name = self.config.providers.recommender
        plugin = get_plugin("recommendations", name)
        if name == "demo":
            service = plugin.Recommender()
        else:
            service = plugin.Recommender(self.config.provider_options[name])
        return service

    @cached_property
    def fixture_recommender(self) -> RecommenderProtocol:
        """Provide fixed assessment for explicitly synthetic evidence."""
        plugin = get_plugin("recommendations", "demo")
        service = plugin.Recommender()
        return service
