"""Resolve the user-visible Sparks collection for BrainStorm history and archival.

Setup owns creation under Assistant. Readers and publishers reuse the same data
source, either named explicitly in local configuration or discovered by title.
"""

from collections.abc import Mapping

from notion_client import Client


def resolve_sparks(client: Client, options: Mapping[str, object], create: bool = False) -> str:
    """Find Sparks, optionally provisioning the collection during explicit setup."""
    configured = options.get("sparks_data_source_id")
    if configured:
        return str(configured)
    parent = options.get("assistant_page_id")
    if not parent:
        raise ValueError("Configure notion.assistant_page_id or notion.sparks_data_source_id and run setup")
    args = {"block_id": str(parent), "page_size": 100}
    while True:
        batch = client.blocks.children.list(**args)
        for block in batch["results"]:
            if block.get("child_database", {}).get("title") == "Sparks":
                db = client.databases.retrieve(database_id=block["id"])
                return db["data_sources"][0]["id"]
        if not batch.get("has_more"):
            break
        args["start_cursor"] = batch["next_cursor"]
    if not create:
        raise ValueError("Sparks is missing under Assistant; run setup")
    db = client.databases.create(
        parent={"type": "page_id", "page_id": str(parent)}, title=[{"text": {"content": "Sparks"}}],
        initial_data_source={"properties": {"Name": {"title": {}}, "Archive Key": {"rich_text": {}}}},
    )
    return db["data_sources"][0]["id"]
