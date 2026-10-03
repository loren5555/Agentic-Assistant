"""Explicitly prepare Notion properties without running models or workflow cycles."""

from assistant.config import load_settings
from logger import get_logger
from providers.notion.archive import ArchiveStore
from providers.notion.workbench import Workbench


def main() -> None:
    """Add required workflow properties and archive keys to configured databases."""
    config = load_settings()
    options = config.provider_options["notion"]
    workbench = Workbench(options)
    archive = ArchiveStore(options)
    workbench.initialize_schema()
    archive.initialize_schema()
    logger = get_logger("providers.notion.setup")
    logger.info("Notion workflow and configured archive properties initialized.")


if __name__ == "__main__":
    main()
