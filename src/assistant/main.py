"""Read one Notion Inbox item and print a decision without executing it."""

import asyncio
import json

from assistant.actions import INBOX_CANDIDATES
from assistant.config import load_settings
from assistant.protocol.inbox import InboxSourceProtocol
from assistant.protocol.router import RouterProtocol
from assistant.schemas.routing import RouterInput
from providers import get_provider
from logger import get_logger


def main() -> None:
    """Read an Inbox item, request an interpretation, and print a suggestion.

    Initialize the decision service only after a nonempty Inbox result. The
    entry never invokes executors or publishers; suggestions require review.
    """
    logger = get_logger("assistant.main")
    config = load_settings()
    inbox_provider = config.providers.inbox
    inbox_options = config.provider_options[inbox_provider]
    provider = get_provider(inbox_provider)

    inbox: InboxSourceProtocol = provider.InboxSource(inbox_options)
    logger.info("Reading the latest Inbox item from %s.", inbox_provider)
    record = inbox.fetch_latest()

    if record is None:
        logger.info("Inbox is empty.")
        return

    # Present the source record and available actions directly to the router.
    request = RouterInput.from_source(
        record,
        context=[],
        candidates=INBOX_CANDIDATES,
    )

    # These actions are suggestions only; no execution capability is attached.
    router_provider = config.providers.router
    router_options = config.provider_options[router_provider]
    provider = get_provider(router_provider)
    router: RouterProtocol = provider.DecisionRouter(router_options)

    logger.info("Interpreting the Inbox item; no actions will be executed.")
    decision = asyncio.run(router.decide(request))

    output = {"inbox": record.model_dump(), "suggestion": decision.model_dump()}
    logger.info(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
