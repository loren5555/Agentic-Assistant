"""Model settings shared by local Pydantic AI capabilities."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class LocalSettings(BaseModel):
    """Configure routing and proposal drafting independently.

    Attributes:
        router_model: Routing model in provider:model format.
        router_effort: Routing reasoning effort, or None for the model default.
        timeout_seconds: Maximum duration of one routing invocation.
        proposer_model: Proposal model in provider:model format.
        proposer_effort: Proposal reasoning effort, or None for the model default.
        proposer_timeout_seconds: Maximum duration of one proposal draft.
        worker_model: Model used for self-contained approved tasks.
        worker_effort: Reasoning effort for task completion.
        worker_timeout_seconds: Maximum duration of one task invocation.
        curator_model: Model extracting reusable accepted outcomes.
        curator_effort: Reasoning effort for curation.
        curator_timeout_seconds: Maximum duration of one extraction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    router_model: str
    router_effort: Literal[
        "none", "minimal", "low", "medium", "high", "xhigh", "max"
    ] | None = "low"
    timeout_seconds: float = 120
    proposer_model: str
    proposer_effort: Literal[
        "none", "minimal", "low", "medium", "high", "xhigh", "max"
    ] | None = "medium"
    proposer_timeout_seconds: float = 180
    worker_model: str
    worker_effort: Literal[
        "none", "minimal", "low", "medium", "high", "xhigh", "max"
    ] | None = "low"
    worker_timeout_seconds: float = 180
    curator_model: str
    curator_effort: Literal[
        "none", "minimal", "low", "medium", "high", "xhigh", "max"
    ] | None = "low"
    curator_timeout_seconds: float = 180
