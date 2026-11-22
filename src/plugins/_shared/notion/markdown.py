"""Read Notion page text and restore embedded bookmarks and link previews."""

import re
from urllib.parse import urlsplit

from notion_client import Client
from logger import get_logger

logger = get_logger("plugins._shared.notion.markdown")

UNKNOWN_BLOCK = re.compile(r'<unknown\b[^>]*\burl="([^"]*)"[^>]*\s*/>')


def page_markdown(client: Client, page_id: str) -> str:
    """Read page text and resolve links omitted by the Markdown API.

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

    # Notion may emit bookmark placeholders without listing their IDs as missing.
    # Only resolve unlisted IDs from Notion block links on the requested page.
    block_ids = {block_id.replace("-", "").lower(): block_id for block_id in missing}
    for match in UNKNOWN_BLOCK.finditer(content):
        if not re.search(r'\salt="bookmark"', match[0]):
            continue
        link = urlsplit(match[1])
        key = link.fragment.replace("-", "").lower()
        if (link.scheme == "https" and link.hostname in {"app.notion.com", "www.notion.so", "notion.so"}
                and link.path.replace("-", "").lower().rstrip("/").endswith(page_id.replace("-", "").lower())
                and re.fullmatch("[0-9a-f]{32}", key)):
            block_ids.setdefault(key, key)

    replacements = {}
    for key, block_id in block_ids.items():
        block = client.blocks.retrieve(block_id=block_id)
        if block["type"] == "bookmark" and block["bookmark"].get("url"):
            bookmark = block["bookmark"]
            caption = "".join(part["plain_text"] for part in bookmark.get("caption", []))
            replacements[key] = f"<{bookmark['url']}>" + (f" — {caption}" if caption else "")
            continue
        if block["type"] != "link_preview":
            raise ValueError(
                f"Incomplete Notion Markdown: page={page_id} block={block_id} "
                f"type={block['type']}; page content remains unread"
            )
        url = block["link_preview"].get("url")
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
        key = match.group(1).rsplit("#", 1)[-1].replace("-", "").lower()
        if key in replacements:
            resolved.add(key)
            return replacements[key]
        return match.group(0)

    content = UNKNOWN_BLOCK.sub(replace_preview, content)
    if resolved != replacements.keys() or "<unknown " in content:
        raise ValueError(f"Unresolved Notion Markdown blocks remain: {page_id}")
    logger.debug("Notion Markdown read: characters=%d linked_blocks=%d.", len(content), len(resolved),
                 extra={"details": {"page": page_id}})
    return content
