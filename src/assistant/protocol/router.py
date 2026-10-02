"""The provider interface for choosing an action without executing it."""

from typing import Protocol

from assistant.schemas.routing import RouterDecision, RouterInput


class RouterProtocol(Protocol):
    """Understand incoming work and suggest an action without executing it."""

    async def decide(self, request: RouterInput) -> RouterDecision:
        """Interpret the input and select one currently available next action.

        Args:
            request: Source material, recalled context, and candidate actions.

        Returns:
            The inferred intent, proposed next step, and selected action.
        """
        ...
