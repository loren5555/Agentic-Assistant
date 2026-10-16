"""Bind provider implementations lazily while exposing application interfaces."""

from functools import cached_property

from assistant.config import AssistantConfig
from assistant.protocol.capture import CapturePublisherProtocol, CaptureSourceProtocol, BriefWriterProtocol
from assistant.protocol.curator import ArchiveStoreProtocol, CuratorProtocol
from assistant.protocol.investigator import InvestigatorProtocol
from assistant.protocol.proposer import ProposerProtocol
from assistant.protocol.router import RouterProtocol
from assistant.protocol.task import TaskWorkerProtocol
from assistant.protocol.workbench import WorkbenchProtocol
from assistant.protocol.recommendation import (
    DiscoveryProtocol, EvidenceReaderProtocol, RecommenderProtocol, ResearchFeedProtocol,
)
from providers import get_provider


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
    def workbench(self) -> WorkbenchProtocol:
        """Provide human review and report storage."""
        name = self.config.providers.workbench
        provider = get_provider(name)
        service = provider.Workbench(self.config.provider_options[name])
        return service

    @cached_property
    def proposer(self) -> ProposerProtocol:
        """Provide item-level proposal drafting."""
        name = self.config.providers.proposer
        provider = get_provider(name)
        service = provider.Proposer(self.config.provider_options[name], workbench=self.workbench)
        return service

    @cached_property
    def router(self) -> RouterProtocol:
        """Provide executable action selection."""
        name = self.config.providers.router
        provider = get_provider(name)
        service = provider.DecisionRouter(self.config.provider_options[name])
        return service

    @cached_property
    def worker(self) -> TaskWorkerProtocol:
        """Provide approved supplied-material task completion."""
        name = self.config.providers.worker
        provider = get_provider(name)
        service = provider.TaskWorker(self.config.provider_options[name])
        return service

    @cached_property
    def investigator(self) -> InvestigatorProtocol:
        """Provide public-source investigation through a replaceable provider."""
        name = self.config.providers.investigator
        provider = get_provider(name)
        service = provider.Investigator(self.config.provider_options[name])
        return service

    @cached_property
    def archive(self) -> ArchiveStoreProtocol:
        """Provide verified Knowledge and Ideas publication."""
        name = self.config.providers.archive
        provider = get_provider(name)
        service = provider.ArchiveStore(self.config.provider_options[name])
        return service

    @cached_property
    def curator(self) -> CuratorProtocol:
        """Provide extraction without controlling workflow progression."""
        name = self.config.providers.curator
        provider = get_provider(name)
        service = provider.Curator(self.config.provider_options[name], self.workbench, self.archive)
        return service

    @cached_property
    def captures(self) -> CaptureSourceProtocol:
        """Provide bounded reads of independent raw Notero and SimpRead inputs."""
        name = self.config.providers.captures
        provider = get_provider(name)
        service = provider.CaptureSource(self.config.provider_options[name])
        return service

    @cached_property
    def briefs(self) -> BriefWriterProtocol:
        """Provide grounded capture organization."""
        name = self.config.providers.briefs
        provider = get_provider(name)
        service = provider.CaptureBriefer(self.config.provider_options[name])
        return service

    @cached_property
    def capture_publisher(self) -> CapturePublisherProtocol:
        """Provide organized Papers and Knowledge publication."""
        name = self.config.providers.captures
        provider = get_provider(name)
        service = provider.CapturePublisher(self.config.provider_options[name])
        return service

    @cached_property
    def feed(self) -> ResearchFeedProtocol:
        """Provide research interests, recommendations, and Interested follow-ups."""
        name = self.config.providers.feed
        provider = get_provider(name)
        service = provider.ResearchFeed(self.config.provider_options[name])
        return service

    @cached_property
    def discovery(self) -> DiscoveryProtocol:
        """Provide candidate discovery; the initial implementation is demo-only."""
        provider = get_provider(self.config.providers.discovery)
        service = provider.Discovery()
        return service

    @cached_property
    def evidence(self) -> EvidenceReaderProtocol:
        """Provide the material actually read for a candidate."""
        provider = get_provider(self.config.providers.evidence)
        service = provider.EvidenceReader()
        return service

    @cached_property
    def recommender(self) -> RecommenderProtocol:
        """Provide evidence-grounded recommendation assessment."""
        name = self.config.providers.recommender
        provider = get_provider(name)
        if name == "demo":
            service = provider.Recommender()
        else:
            service = provider.Recommender(self.config.provider_options[name])
        return service
