"""Local Pydantic AI implementation of the routing interface."""

import asyncio
import json
from collections.abc import Mapping
from time import perf_counter

from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models import infer_model
from pydantic_ai.models.openai import OpenAIResponsesModelSettings

from assistant.protocol.router import RouterProtocol
from assistant.schemas.routing import RouterDecision, RouterInput
from providers.routing import ROUTER_INSTRUCTIONS, validate_decision
from logger import get_logger
from providers.local.config import LocalSettings


class DecisionRouter(RouterProtocol):
    """Use a Pydantic AI model to understand input and propose the next action.

    Attributes:
        agent: Model-backed agent with the Assistant's decision instructions.
        model: Configured provider and model identifier.
        effort: Configured reasoning effort, or None for the model default.
        timeout_seconds: Maximum time allowed for one decision.
    """

    def __init__(self, options: Mapping[str, object]) -> None:
        """Construct the decision agent using the configured model.

        Args:
            options: Model settings from application configuration.
        """
        settings = LocalSettings.model_validate(options)
        self.model = settings.router_model
        self.effort = settings.router_effort
        self.timeout_seconds = settings.timeout_seconds
        self.logger = get_logger("assistant.local.router")

        # The openai-codex provider owns subscription authentication; no CLI runs.
        model = infer_model(self.model)
        model_settings = OpenAIResponsesModelSettings()
        if self.effort is not None:
            model_settings["openai_reasoning_effort"] = self.effort

        # Native structured output supplies a schema without an output-call tool.
        self.agent = Agent(
            model,
            output_type=NativeOutput(RouterDecision),
            instructions=ROUTER_INSTRUCTIONS,
            model_settings=model_settings,
        )

    async def decide(self, request: RouterInput) -> RouterDecision:
        """Interpret one request without executing the proposed action.

        Args:
            request: Source material, recalled context, and available actions.

        Returns:
            A structured interpretation and an available next-action proposal.
        """
        prompt = request.model_dump_json()
        self.logger.info(
            f"Requesting a local decision: model={self.model}, effort={self.effort}."
        )
        started_at = perf_counter()

        # Each invocation owns HTTP resources and has an overall time limit.
        async with asyncio.timeout(self.timeout_seconds):
            async with self.agent:
                response = await self.agent.run(prompt)

        decision = response.output
        validated_decision = validate_decision(request, decision)

        reported_usage = response.usage
        usage = {
            "input_tokens": reported_usage.input_tokens,
            "cached_input_tokens": reported_usage.cache_read_tokens,
            "output_tokens": reported_usage.output_tokens,
            "requests": reported_usage.requests,
        }
        elapsed_seconds = perf_counter() - started_at
        usage_summary = json.dumps(usage, indent=2)
        self.logger.info(
            f"Local decision completed in {elapsed_seconds:.2f} seconds.\n"
            f"Token usage:\n{usage_summary}"
        )

        return validated_decision
