"""Model and invocation settings shared by Codex capabilities."""

from pydantic import BaseModel, ConfigDict, Field


class CodexSettings(BaseModel):
    """Configure independent routing, investigation and public research invocations.

    Attributes:
        router_model: Routing model identifier, or None for the CLI default.
        router_effort: Routing reasoning effort, or None for the CLI default.
        timeout_seconds: Maximum routing invocation duration.
        executable: Codex CLI executable name or path.
        investigator_model: Investigation model identifier.
        investigator_effort: Investigation reasoning effort.
        investigator_timeout_seconds: Maximum investigation invocation duration.
        discovery_model: Candidate search model, falling back to investigator_model.
        discovery_effort: Search effort, falling back to investigator_effort.
        discovery_timeout_seconds: Search deadline including web tool use.
        discovery_max_candidates: Upper bound on discovered candidates per day.
        discovery_recent_days: Recent-paper window ending on the requested day.
        evidence_model: Reading model, falling back to investigator_model.
        evidence_effort: Reading effort, falling back to investigator_effort.
        evidence_timeout_seconds: Deadline for reading one candidate.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    router_model: str | None = None
    router_effort: str | None = None
    timeout_seconds: float = 120
    executable: str = "codex"
    investigator_model: str | None = None
    investigator_effort: str | None = None
    investigator_timeout_seconds: float = 300

    discovery_model: str | None = None
    discovery_effort: str | None = None
    discovery_timeout_seconds: float = Field(default=600, gt=0)
    discovery_max_candidates: int = Field(default=60, ge=1, le=100)
    discovery_recent_days: int = Field(default=7, ge=1)
    evidence_model: str | None = None
    evidence_effort: str | None = None
    evidence_timeout_seconds: float = Field(default=180, gt=0)
