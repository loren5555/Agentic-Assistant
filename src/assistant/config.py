"""Read service providers and their settings from application configuration."""

from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator
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

    brainstorm: str = "codex"
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


class CollectorSettings(BaseModel):
    """Bound weekly exploration and daily source collection costs."""

    deep_provider: str = "codex"
    light_provider: str = "local"
    deep_weekday: int = Field(default=6, ge=0, le=6)
    max_queries: int = Field(default=6, ge=1, le=20)
    max_candidates: int = Field(default=40, ge=1, le=100)
    context_pool_size: int = Field(default=30, ge=1, le=100)
    frontier_days: int = Field(default=90, ge=1)


class RecommendationSettings(BaseModel):
    """Configure newspaper cache size and exploratory editorial coverage.

    Attributes:
        pool_size: Recent visible cache capacity; explicit likes are preserved.
        selected_count: Maximum selected entries in a daily edition.
        reading_budget: Maximum shortlisted candidates to read per edition.
        exploration: Long-term target weights across core and exploratory fields.
    """

    pool_size: int = Field(default=100, ge=10, le=500)
    selected_count: int = Field(default=5, ge=1, le=10)
    reading_budget: int = Field(default=15, ge=1, le=50)
    exploration: dict[str, float] = Field(default_factory=lambda: {
        "Core": .4, "Broader": .3, "Neighboring": .2, "Cross-disciplinary": .1,
    })
    ages: dict[str, float] = Field(default_factory=lambda: {
        "week": .05, "month": .15, "quarter": .20, "half_year": .15,
        "year": .15, "three_years": .15, "older": .15,
    })
    coverage_days: int = Field(default=90, ge=1)
    collector: CollectorSettings = Field(default_factory=CollectorSettings)

    @model_validator(mode="after")
    def validate_distribution(self):
        """Require recognizable, nonnegative weights with a positive total."""
        from assistant.components.recommendations.discovery.models import BREADTHS
        from assistant.components.recommendations.collector.policy import AGES
        for weights, names in ((self.exploration, BREADTHS), (self.ages, AGES)):
            if set(weights) != set(names) or any(v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
                raise ValueError(f"Distribution must contain nonnegative weights for {names}, with a positive total")
        return self


class ServiceSettings(BaseModel):
    """Configure the single-host execution service and its CLI clients.

    Attributes:
        port: Loopback HTTP port shared by serve and CLI requests.
    """

    model_config = ConfigDict(extra="forbid")
    port: int = Field(default=8765, ge=1024, le=65535)


class ScheduleSettings(BaseModel):
    """Persist one job's recurrence, time zone and enabled state."""

    model_config = ConfigDict(extra="forbid")
    cron: str = Field(min_length=1, max_length=160)
    timezone: str = "Asia/Shanghai"
    enabled: bool = True

    @model_validator(mode="after")
    def validate_schedule(self):
        """Use six second-first fields and require an actual future occurrence."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from croniter import croniter

        if len(self.cron.split()) != 6:
            raise ValueError(
                "Use six cron fields: second minute hour day month weekday"
            )
        try:
            zone = ZoneInfo(self.timezone)
            iterator = croniter(
                self.cron,
                datetime.now(zone),
                second_at_beginning=True,
                max_years_between_matches=8,
            )
            iterator.get_next(datetime)
        except Exception as error:
            raise ValueError(
                "Invalid cron/timezone or no occurrence within eight years"
            ) from error
        return self


def schedule_settings(value: str | ScheduleSettings) -> ScheduleSettings:
    """Normalize the compact YAML form for runtime and browser consumers."""
    return ScheduleSettings(cron=value) if isinstance(value, str) else value


class RuntimeSettings(BaseModel):
    """Configure local durability and explicitly opt into recurring jobs.

    Attributes:
        directory: Local directory for databases and reports.
        batch_size: Maximum raw capture records per manual pass.
        schedules: Enabled job names and cron expressions; empty means manual only.
        recommendations: Initial newspaper topics, pool size and exploratory mix.
        recommendation_maxima: Optional per-category caps, never output quotas.
        service: Local HTTP service endpoint used by serve and CLI clients.
    """

    directory: str = "data/assistant"
    batch_size: int = 20
    schedules: dict[str, str | ScheduleSettings] = Field(default_factory=dict)
    recommendations: RecommendationSettings = Field(
        default_factory=RecommendationSettings
    )
    recommendation_maxima: dict[str, int] = Field(default_factory=dict)
    service: ServiceSettings = Field(default_factory=ServiceSettings)


class AssistantConfig(BaseModel):
    """Complete configuration consumed by the application entry.

    Attributes:
        providers: Provider selections for the application's capabilities.
        provider_options: Opaque options keyed by provider package name. Each
            provider interprets and validates its own settings when opened.
        runtime: Local persistence, batching, and explicitly enabled schedules.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    _source: Path | None = PrivateAttr(default=None)

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
    assistant_config._source = Path(str(config_file)).resolve()
    return assistant_config
