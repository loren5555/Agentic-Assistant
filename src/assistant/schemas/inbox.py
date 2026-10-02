"""Content retrieved from an inbox source."""

from pydantic import BaseModel, ConfigDict, Field


class InboxRecord(BaseModel):
    """Text content and source information retrieved from an Inbox.

    Attributes:
        source: Source system name, such as notion.
        source_id: Nonempty record ID in the source system.
        text: Nonempty text for downstream processing; Notion combines the title
            and Markdown body.
        revision: Source revision identifier; Notion uses the last edited time.
        simulated: Whether the record is simulated; defaults to False for real data.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    source_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    revision: str | None = None
    simulated: bool = False

    @property
    def context_content(self) -> str:
        """Provide the inbox content without its storage metadata.

        Returns:
            Record text for model context.
        """
        content = self.text
        return content
