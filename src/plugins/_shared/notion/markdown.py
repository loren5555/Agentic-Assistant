"""Read complete Markdown through an operation-owned Notion client."""

from notion_client import Client


def page_markdown(client: Client, page_id: str) -> str:
    """Read complete page content rather than silently using an incomplete export.

    Args:
        client: Connection owned by the surrounding operation.
        page_id: Page to read.

    Returns:
        Complete captured Markdown.
    """
    response = client.pages.retrieve_markdown(page_id=page_id)
    if response["truncated"] or response["unknown_block_ids"]:
        raise ValueError(f"Incomplete capture Markdown: {page_id}")
    content = response["markdown"]
    return content
