"""Task content and its optional references to external sources."""

from pydantic import BaseModel, ConfigDict, Field


class SourceReference(BaseModel):
    """Identify a source within its namespace, optionally at a revision."""

    model_config = ConfigDict(frozen=True)

    namespace: str
    id: str
    revision: str | None = None


class WorkInput(BaseModel):
    """Describe work independently of the channel that supplied it."""

    text: str
    sources: list[SourceReference] = Field(default_factory=list)
    simulated: bool = False

    @property
    def context_content(self) -> str:
        """Provide the work content without its source references.

        Returns:
            Task text for model context.
        """
        content = self.text
        return content
