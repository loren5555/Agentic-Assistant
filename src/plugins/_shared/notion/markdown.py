"""Read page text while representing Notion link previews explicitly."""

import re

from notion_client import Client
from logger import get_logger

logger = get_logger("plugins.notion.markdown")

UNKNOWN_BLOCK = re.compile(r'<unknown\b[^>]*\burl="([^"]*)"[^>]*\s*/>')


def page_markdown(client: Client, page_id: str) -> str:
    """Read page text and resolve link previews omitted by the Markdown API.

    Args:
        client: Connection owned by the surrounding operation.
        page_id: Page to read.

    Returns:
        Captured Markdown, including links or explicit unavailable-preview notices.
    """
    logger.debug("Reading Notion Markdown.", extra={"details": {"page": page_id}})
    response = client.pages.retrieve_markdown(page_id=page_id)
    content = response["markdown"]
    missing = response["unknown_block_ids"]
    if response["truncated"] and not missing:
        raise ValueError(f"Notion Markdown is truncated without recoverable block IDs: {page_id}")

    replacements = {}
    for block_id in missing:
        block = client.blocks.retrieve(block_id=block_id)
        if block["type"] != "link_preview":
            raise ValueError(
                f"Incomplete Notion Markdown: page={page_id} block={block_id} "
                f"type={block['type']}; page content remains unread"
            )
        url = block["link_preview"].get("url")
        key = block_id.replace("-", "")
        if url:
            replacements[key] = f"<{url}>"
            logger.debug("Recovered a link preview URL.", extra={"details": {"page": page_id, "block": block_id}})
        else:
            block_url = f"https://www.notion.so/{page_id.replace('-', '')}#{key}"
            replacements[key] = f"[Link preview unavailable through the Notion API]({block_url})"
            logger.warning(
                "Notion returned a link preview without its URL; retaining a notice and block link.",
                extra={"details": {"page": page_id, "block": block_id}},
            )

    resolved = set()

    def replace_preview(match: re.Match[str]) -> str:
        """Replace a preview in place, retaining its position in the page."""
        key = match.group(1).rsplit("#", 1)[-1].replace("-", "")
        if key in replacements:
            resolved.add(key)
            return replacements[key]
        return match.group(0)

    content = UNKNOWN_BLOCK.sub(replace_preview, content)
    if resolved != replacements.keys() or "<unknown " in content:
        raise ValueError(f"Unresolved Notion Markdown blocks remain: {page_id}")
    logger.debug("Notion Markdown read: characters=%d link_previews=%d.", len(content), len(resolved),
                 extra={"details": {"page": page_id}})
    return content
