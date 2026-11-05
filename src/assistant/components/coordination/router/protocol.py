"""Routing capability and context-bearing source interface."""

from typing import Protocol

from assistant.components.coordination.router.models import RouterDecision, RouterInput


class RouterProtocol(Protocol):
    """Select one capability before a proposal is reviewed."""

    async def decide(self, request: RouterInput) -> RouterDecision:
        """Interpret the input and select one currently available next action.

        Args:
            request: Source material, recalled context, and candidate actions.

        Returns:
            The selected action identifier and optional invocation telemetry.
        """
        ...
