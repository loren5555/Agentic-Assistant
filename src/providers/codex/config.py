"""Model and invocation settings shared by Codex capabilities."""

from pydantic import BaseModel, ConfigDict


class CodexSettings(BaseModel):
    """Configure independent routing and investigation invocations.

    Attributes:
        router_model: Routing model identifier, or None for the CLI default.
        router_effort: Routing reasoning effort, or None for the CLI default.
        timeout_seconds: Maximum routing invocation duration.
        executable: Codex CLI executable name or path.
        investigator_model: Investigation model identifier.
        investigator_effort: Investigation reasoning effort.
        investigator_timeout_seconds: Maximum investigation invocation duration.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    router_model: str | None = None
    router_effort: str | None = None
    timeout_seconds: float = 120
    executable: str = "codex"
    investigator_model: str | None = None
    investigator_effort: str | None = None
    investigator_timeout_seconds: float = 300
