"""Notion connection and collection settings for storage capabilities."""

from pydantic import BaseModel


class NotionSettings(BaseModel):
    """Connection settings for the three proposal workflow data sources.

    Attributes:
        token: Notion integration token.
        inbox_data_source_id: Inbox data source queried for unarchived inputs.
        todo_data_source_id: TODO data source queried for elevated inputs.
        workbench_data_source_id: Data source containing proposals and reviews.
        input_limit: Maximum number of Inbox and TODO items read per collection.
    """

    token: str
    inbox_data_source_id: str
    todo_data_source_id: str
    workbench_data_source_id: str
    input_limit: int = 20


class ArchiveSettings(BaseModel):
    """Configure the long-term databases independently from Workbench.

    Attributes:
        token: Notion integration token.
        knowledge_data_source_id: Destination for reusable knowledge.
        ideas_data_source_id: Destination for research ideas.
    """

    token: str
    knowledge_data_source_id: str = ""
    ideas_data_source_id: str = ""


class ResearchFeedSettings(BaseModel):
    """Configure existing research databases and their user-visible columns.

    Attributes:
        token: Integration token, never included in reports.
        research_interests_data_source_id: Read-only priorities.
        research_feed_data_source_id: Recommendation destination.
        inbox_data_source_id: Interested-feedback follow-up destination.
        interests_status_property: Existing interest select/status column.
        interests_active_value: Value identifying active interests.
        feed_category_property: Existing recommendation category column.
        feed_feedback_property: Human-maintained feedback column.
    """

    token: str
    research_interests_data_source_id: str = "48f7a170-0249-4c12-aa37-0c33c54f06cc"
    research_feed_data_source_id: str = "ba262e5f-d58d-4f63-a77a-1f27e72b087e"
    inbox_data_source_id: str
    interests_status_property: str = "Status"
    interests_active_value: str = "Active"
    feed_category_property: str = "Type"
    feed_feedback_property: str = "Human Feedback"


class CaptureSettings(BaseModel):
    """Configure independent raw inputs and organized output collections.

    Attributes:
        token: Notion integration token.
        notero_data_source_id: Read-only Zotero-synced raw input.
        simpread_data_source_id: Independent article capture collection.
        papers_data_source_id: Organized paper briefs and human discussions.
        knowledge_data_source_id: Reusable explanations and methods.
    """

    token: str
    notero_data_source_id: str = "2f9835de-f60d-81f7-89e4-000bb7ff2dba"
    simpread_data_source_id: str = "1a9835de-f60d-8109-8b50-000b7d486414"
    papers_data_source_id: str = "3b8835de-f60d-835d-8c98-07c38b24fa6a"
    knowledge_data_source_id: str = ""
