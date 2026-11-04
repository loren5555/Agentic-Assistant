"""Local Pydantic AI implementation of the routing interface."""

from collections.abc import Mapping
from time import perf_counter
import asyncio

from pydantic_ai import Agent, NativeOutput
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models import infer_model
from pydantic_ai.models.openai import OpenAIResponsesModelSettings

from assistant.components.router.models import RouterDecision, RouterInput
from assistant.components.router.prompt import ROUTER_INSTRUCTIONS, validate_decision
from assistant.components.router.protocol import RouterProtocol
from logger import get_logger, trace_call
from assistant.runtime.records import ExecutionProcess
from plugins._shared.local.config import LocalSettings


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
        self.logger = get_logger("plugins.router.local")

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

    @trace_call("component", "router.decide")
    async def decide(self, request: RouterInput) -> RouterDecision:
        """Interpret one request without executing the proposed action.

        Args:
            request: Source material, recalled context, and available actions.

        Returns:
            A structured interpretation and an available next-action proposal.
        """
        prompt = request.model_dump_json()
        self.logger.info(
            f"kind=agent provider=local action=decide Requesting a local decision: model={self.model}, effort={self.effort}."
        )
        started_at = perf_counter()

        # Each invocation owns HTTP resources and has an overall time limit.
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with self.agent:
                    response = await self.agent.run(prompt)
        except asyncio.CancelledError:
            self.logger.warning("kind=agent provider=local action=decide Agent invocation cancelled: elapsed=%.2fs.", perf_counter() - started_at)
            raise
        except Exception:
            self.logger.exception("kind=agent provider=local action=decide Agent invocation failed: elapsed=%.2fs.", perf_counter() - started_at)
            raise

        decision = response.output
        validated_decision = validate_decision(request, decision)

        reported_usage = response.usage
        usage = {
            "input_tokens": reported_usage.input_tokens,
            "cached_input_tokens": reported_usage.cache_read_tokens,
            "output_tokens": reported_usage.output_tokens,
            "requests": reported_usage.requests,
        }
        validated_decision.process = ExecutionProcess(
            events=ModelMessagesTypeAdapter.dump_python(response.all_messages(), mode="json"),
            usage=usage,
        )
        elapsed_seconds = perf_counter() - started_at
        self.logger.info(
            f"kind=agent provider=local action=decide Local decision completed in {elapsed_seconds:.2f} seconds.",
            extra={"details": {"token_usage": usage}},
        )

        return validated_decision
