"""Parse the command, acquire local ownership, and launch the application."""

import os
import asyncio
import fcntl
from pathlib import Path

from assistant.cli import arguments
from assistant.config import load_settings
from logger import configure_logging, get_logger


os.environ["PYDANTIC_AI_NO_BANNER"] = "1"


def main() -> None:
    """Route clients to HTTP; reserve exclusive local ownership for serve/setup."""
    options = arguments()
    configure_logging(verbose=options.verbose)
    logger = get_logger("main")
    try:
        settings = load_settings(options.config)
        directory = Path(settings.runtime.directory).resolve()
        logger.info(
            'Command selected: command=%s job=%s.',
            options.command,
            getattr(options, 'job', 'none'),
            extra={"details": {'runtime_directory': directory / "v2"}},
        )

        if options.command in {"run", "status", "resume"}:
            from assistant.commands import run, status, resume
            handler = {"run": run.run, "status": status.run, "resume": resume.run}[options.command]
            asyncio.run(handler(settings, options))
        else:
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / "runtime.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise RuntimeError("This runtime is already in use. Keep serve running for run/status/resume; stop it before setup.") from error
                if options.command == "serve":
                    from assistant.runtime.application import Application
                    asyncio.run(Application(settings).execute(options))
                elif options.command == "setup":
                    from types import SimpleNamespace
                    from assistant.commands import setup
                    from assistant.runtime.services import Services
                    asyncio.run(setup.run(SimpleNamespace(settings=settings, services=Services(settings)), options))

    except KeyboardInterrupt:
        logger.info("Assistant interrupted by user.")
    except Exception as error:
        logger.exception("Command failed: %s", error)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
