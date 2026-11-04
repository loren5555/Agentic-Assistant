"""Notion connection and collection settings for storage capabilities."""

from pydantic import BaseModel


class NotionSettings(BaseModel):
    """Connection settings used by the Workbench storage component.

    Attributes:
        token: Notion integration token.
        workbench_data_source_id: Data source containing proposals and reviews.
    """

    token: str
    workbench_data_source_id: str


class ArchiveSettings(BaseModel):
    """Configure the long-term databases independently from Workbench.

    Attributes:
        token: Notion integration token.
        knowledge_data_source_id: Destination for reusable knowledge.
        ideas_data_source_id: Destination for research ideas.
        research_interests_data_source_id: Destination for accepted research interests.
    """

    token: str
    knowledge_data_source_id: str = ""
    ideas_data_source_id: str = ""
    research_interests_data_source_id: str = "48f7a170-0249-4c12-aa37-0c33c54f06cc"


class ResearchFeedSettings(BaseModel):
    """Configure existing research databases and their user-visible columns.

    Attributes:
        token: Integration token, never included in reports.
        research_interests_data_source_id: Read-only priorities.
        research_feed_data_source_id: Recommendation destination.
        papers_data_source_id: Human-marked paper recommendation preferences.
        interests_status_property: Existing interest select/status column.
        interests_active_value: Value identifying active interests.
        feed_category_property: Existing recommendation category column.
        feed_feedback_property: Human-maintained feedback column.
    """

    token: str
    research_interests_data_source_id: str = "48f7a170-0249-4c12-aa37-0c33c54f06cc"
    research_feed_data_source_id: str = "ba262e5f-d58d-4f63-a77a-1f27e72b087e"
    papers_data_source_id: str = "3b8835de-f60d-835d-8c98-07c38b24fa6a"
    discovery_pool_data_source_id: str = ""
    assistant_page_id: str = ""
    interests_status_property: str = "Status"
    interests_active_value: str = "Active"
    feed_category_property: str = "Type"
    feed_feedback_property: str = "Human Feedback"


class CaptureSettings(BaseModel):
    """Configure independent raw inputs and organized output collections.

    Attributes:
        token: Notion integration token.
        notero_data_source_id: Zotero-synced input with assistant-owned flags.
        simpread_data_source_id: Independent article capture collection.
        papers_data_source_id: Organized paper briefs and human discussions.
        knowledge_data_source_id: Reusable explanations and methods.
    """

    token: str
    notero_data_source_id: str = "2f9835de-f60d-81f7-89e4-000bb7ff2dba"
    simpread_data_source_id: str = "1a9835de-f60d-8109-8b50-000b7d486414"
    papers_data_source_id: str = "3b8835de-f60d-835d-8c98-07c38b24fa6a"
    knowledge_data_source_id: str = ""
