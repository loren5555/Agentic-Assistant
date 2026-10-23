"""Parse the command, acquire local ownership, and launch the application."""

import os
import asyncio
import fcntl
from pathlib import Path

from assistant.cli import arguments
from assistant.config import load_settings
from assistant.runtime.application import Application
from logger import get_logger


os.environ["PYDANTIC_AI_NO_BANNER"] = "1"


def main() -> None:
    """Launch the command selected by the user under one local runtime lock."""
    options = arguments()
    settings = load_settings(options.config)
    directory = Path(settings.runtime.directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    logger = get_logger("main")
    logger.info("Command selected: command=%s job=%s runtime_directory=%s.",
                options.command, getattr(options, "job", "none"), directory)

    with (directory / "runtime.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        application = Application(settings)
        try:
            asyncio.run(application.execute(options))
        except KeyboardInterrupt:
            logger.info("Assistant interrupted by user.")


if __name__ == "__main__":
    main()
