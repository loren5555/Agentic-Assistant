"""Initialize specific Notion properties with independent schema readback."""

from notion_client import Client


def ensure_rich_text(client: Client, data_source_id: str, name: str) -> None:
    """Create a missing text property and verify the resulting schema.

    Args:
        client: Connection owned by the storage component.
        data_source_id: Collection requiring a stable publication identity.
        name: Text property used by that component.
    """
    source = client.data_sources.retrieve(data_source_id=data_source_id)
    if name not in source["properties"]:
        client.data_sources.update(data_source_id=data_source_id,
                                   properties={name: {"rich_text": {}}})
        verified = client.data_sources.retrieve(data_source_id=data_source_id)
        if verified["properties"][name]["type"] != "rich_text":
            raise ValueError(f"Schema readback failed for {name}: {data_source_id}")


def ensure_select_option(client: Client, data_source_id: str, name: str, value: str) -> None:
    """Append a lifecycle option and verify it without removing existing choices.

    Args:
        client: Connection owned by the storage component.
        data_source_id: Workbench collection.
        name: Existing select property.
        value: Additional option needed by the workflow.
    """
    source = client.data_sources.retrieve(data_source_id=data_source_id)
    options = source["properties"][name]["select"]["options"]
    if value not in {option["name"] for option in options}:
        client.data_sources.update(
            data_source_id=data_source_id,
            properties={name: {"select": {"options": [*options, {"name": value}]}}},
        )
        verified = client.data_sources.retrieve(data_source_id=data_source_id)
        stored_options = verified["properties"][name]["select"]["options"]
        if value not in {option["name"] for option in stored_options}:
            raise ValueError(f"Schema option readback failed for {name}: {data_source_id}")
