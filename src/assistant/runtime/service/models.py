"""Define the local request contract and identify the selected runtime.

Input origin: CLI arguments or HTTP JSON; no provider configuration is accepted.
Output destination: validated submissions and JSON reports for local clients.
"""

from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

JobName = Literal[
    "brainstorm-material",
    "brainstorm-idea",
    "propose-tasks",
    "organize-papers",
    "organize-articles",
    "process-signals",
    "reconcile-feedback",
    "process-workbench",
    "recommend-papers",
    "recommend-papers-deep",
    "recommend-papers-light",
]
TERMINAL_STATES = {"SUCCESS", "ERROR", "CANCELLED", "MAX_RECOVERY_ATTEMPTS_EXCEEDED"}
RUNTIME_HEADER = "X-Assistant-Runtime"


def runtime_identity(directory: str) -> str:
    """Return the absolute data directory used to reject wrong-service requests."""
    return str(Path(directory).resolve() / "v2")


class JobSubmission(BaseModel):
    """Request one named task; reusing a request ID retries submission, not work.

    Attributes:
        job: Supported business entry point.
        page: Optional single source selection for paper/article intake.
        request_id: Stable identity returned by the CLI before contacting serve.
    """

    model_config = ConfigDict(extra="forbid")
    job: JobName
    page: str | None = None
    request_id: UUID = Field(default_factory=uuid4)

    @model_validator(mode="after")
    def check_page_job(self):
        """Allow page selection only for jobs whose workflow accepts it."""
        if self.page is not None and self.job not in {
            "brainstorm-material",
            "brainstorm-idea",
            "organize-papers",
            "organize-articles",
        }:
            raise ValueError(
                "page is supported only for organize-papers, organize-articles and BrainStorm jobs"
            )
        if self.page is not None and self.job in {"brainstorm-material", "brainstorm-idea"}:
            try:
                UUID(self.page)
            except ValueError:
                raise ValueError(
                    "--page requires a Notion page ID (32 hexadecimal digits, with or without hyphens). "
                    "Omit --page to let BrainStorm choose a starting point."
                ) from None
        return self


class RecoverySubmission(BaseModel):
    """Identify one recoverable workflow and an idempotent recovery request."""

    model_config = ConfigDict(extra="forbid")
    request_id: UUID = Field(default_factory=uuid4)
