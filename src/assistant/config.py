"""Read service providers and their settings from application configuration."""

from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from yaml import safe_load


class ProviderSettings(BaseModel):
    """Select the providers implementing the application's external capabilities.

    Attributes:
        processors: Provider owning independent source extraction and writeback.
        organizer: Shared source understanding and information organization.
        reconciler: Deterministic human feedback interpretation.
        router: Provider package exposing the decision service.
        investigator: Provider package exposing read-only question investigation.
        proposer: Provider package managing proposals.
        workbench: Provider package storing reports and reading their sources.
        worker: Provider completing self-contained approved tasks.
        curator: Provider finalizing human-accepted results.
        publisher: Provider storing accepted typed information products.
        discovery_pool: Provider storing broad recent research discoveries.
        direction_proposer: Capability developing research direction proposals.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    router: str
    investigator: str
    proposer: str = "local"
    workbench: str = "notion"
    worker: str = "local"
    curator: str = "local"
    briefs: str = "local"
    feed: str = "notion"
    discovery_pool: str = "notion"
    discovery: str = "demo"
    evidence: str = "demo"
    recommender: str = "local"
    processors: str = "notion"
    organizer: str = "local"
    reconciler: str = "local"
    publisher: str = "notion"
    direction_proposer: str = "local"
    planner: str = "local"


class RecommendationSettings(BaseModel):
    """Configure newspaper topics, cache size and exploratory editorial coverage.

    Attributes:
        topics: Initial user-selected topics, independent of approved proposals.
        pool_size: Recent visible cache capacity; explicit likes are preserved.
        selected_count: Maximum selected entries in a daily edition.
        reading_budget: Maximum shortlisted candidates to read per edition.
        exploration: Long-term target weights across core and exploratory fields.
    """

    topics: list[str] = Field(default_factory=list)
    pool_size: int = Field(default=100, ge=10, le=500)
    selected_count: int = Field(default=5, ge=1, le=10)
    reading_budget: int = Field(default=15, ge=1, le=50)
    exploration: dict[str, float] = Field(default_factory=lambda: {
        "Core": .4, "Broader": .3, "Neighboring": .2, "Cross-disciplinary": .1,
    })


class RuntimeSettings(BaseModel):
    """Configure local durability and explicitly opt into recurring jobs.

    Attributes:
        directory: Local directory for databases and reports.
        batch_size: Maximum raw capture records per manual pass.
        schedules: Enabled job names and cron expressions; empty means manual only.
        recommendations: Initial newspaper topics, pool size and exploratory mix.
        recommendation_maxima: Optional per-category caps, never output quotas.
    """

    directory: str = "data/assistant"
    batch_size: int = 20
    schedules: dict[str, str] = {}
    recommendations: RecommendationSettings = Field(default_factory=RecommendationSettings)
    recommendation_maxima: dict[str, int] = Field(default_factory=dict)


class AssistantConfig(BaseModel):
    """Complete configuration consumed by the application entry.

    Attributes:
        providers: Provider selections for the application's capabilities.
        provider_options: Opaque options keyed by provider package name. Each
            provider interprets and validates its own settings when opened.
        runtime: Local persistence, batching, and explicitly enabled schedules.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    providers: ProviderSettings
    provider_options: dict[str, dict[str, object]]
    runtime: RuntimeSettings = RuntimeSettings()


def load_settings(path: str | Path | None = None) -> AssistantConfig:
    """Read config.yaml from the assistant package and parse application settings.

    Args:
        path: Optional YAML path for an isolated debug configuration.

    Returns:
        Provider selections and options, without initializing any services.
    """

    config_file = Path(path) if path is not None else files("assistant") / "config.yaml"
    with config_file.open("r", encoding="utf-8") as stream:
        document = safe_load(stream)

    # Keep the existing YAML layout: providers selects packages, and the other
    # top-level sections belong to those packages rather than to the Assistant.
    providers = document.pop("providers")
    runtime = document.pop("runtime", {})
    assistant_config = AssistantConfig(
        providers=providers,
        provider_options=document,
        runtime=runtime,
    )
    return assistant_config
