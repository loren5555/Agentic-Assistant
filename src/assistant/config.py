"""Read service providers and their settings from application configuration."""

from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from yaml import safe_load


class ProviderSettings(BaseModel):
    """Select the providers implementing the application's external capabilities.

    Attributes:
        inbox: Inbox provider package name, identifying a subpackage of providers.
        router: Provider package exposing the decision service.
        investigator: Provider package exposing read-only question investigation.
        proposer: Provider package managing proposals.
        workbench: Provider package storing reports and reading their sources.
        worker: Provider completing self-contained approved tasks.
        execution: Provider owning the approved-task execution cycle.
        curator: Provider finalizing human-accepted results.
        archive: Provider storing retained knowledge and ideas.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    inbox: str
    router: str
    investigator: str
    proposer: str = "local"
    workbench: str = "notion"
    worker: str = "local"
    execution: str = "local"
    curator: str = "local"
    archive: str = "notion"
    captures: str = "notion"
    briefs: str = "local"
    feed: str = "notion"
    discovery: str = "demo"
    evidence: str = "demo"
    recommender: str = "local"


class RuntimeSettings(BaseModel):
    """Configure local durability and explicitly opt into recurring jobs.

    Attributes:
        directory: Local directory for databases and reports.
        batch_size: Maximum raw capture records per manual pass.
        schedules: Enabled job names and cron expressions; empty means manual only.
        recommendation_maxima: Daily upper bounds, never required output counts.
    """

    directory: str = "data/assistant"
    batch_size: int = 20
    schedules: dict[str, str] = {}
    recommendation_maxima: dict[str, int] = {
        "Understanding Daily": 1, "Mainline Deep Read": 1,
        "Frontier Radar": 1, "Exceptional Event": 1,
    }


class AssistantConfig(BaseModel):
    """Complete configuration consumed by the application entry.

    Attributes:
        providers: Provider selections for the application's capabilities.
        provider_options: Opaque options keyed by provider package name. Each
            provider interprets and validates its own settings when opened.
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
