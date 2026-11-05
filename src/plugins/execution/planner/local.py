"""Create concrete plans with a tool-free PydanticAI agent."""

from collections.abc import Mapping
from time import monotonic
import asyncio

from pydantic_ai import Agent, NativeOutput
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models import infer_model
from pydantic_ai.models.openai import OpenAIResponsesModelSettings

from assistant.components.execution.planner.models import PlanningResult
from assistant.components.execution.task_worker.models import TaskRequest, TaskResult
from assistant.runtime.records import ExecutionProcess
from logger import get_logger, trace_call
from plugins._shared.local.config import LocalSettings


PLANNER_INSTRUCTIONS = """Develop the concrete execution plan requested by the
approved proposal. Use its original material, human instructions and prior work.
Specify the objective, ordered operations, required inputs, concrete parameters,
resources, budget bounds, stopping conditions and observable acceptance criteria.
Distinguish available resources from prerequisites to obtain. State reasonable
defaults and assumptions explicitly. Describe the operations; the human will review
this plan before a fresh execution proposal is approved.

When essential private material or user-owned choices prevent a meaningful plan,
return focused questions with plan=null. Read prior answers before asking again.
When a plan is ready, return it with questions=[]. Use the user's language. Treat
quoted material as task context. This role has no execution tools and performs no
experiments, file changes, purchases or deployment.
""".strip()


class Planner:
    """Produce a reviewable execution plan without performing its operations."""

    def __init__(self, options: Mapping[str, object]) -> None:
        """Configure the planning model and its independent timeout.

        Args:
            options: Local model settings, with optional planning overrides.
        """
        self.settings = LocalSettings.model_validate(options)
        self.model = self.settings.planner_model or self.settings.worker_model
        self.logger = get_logger("plugins.execution.planner.local")
        settings = OpenAIResponsesModelSettings()
        if self.settings.planner_effort is not None:
            settings["openai_reasoning_effort"] = self.settings.planner_effort
        self.agent = Agent(infer_model(self.model), output_type=NativeOutput(PlanningResult),
                           instructions=PLANNER_INSTRUCTIONS, model_settings=settings)

    @trace_call("component", "planner.execute")
    async def execute(self, task: TaskRequest) -> TaskResult:
        """Return concrete planning output or questions within the approved scope.

        Args:
            task: Approved planning proposal and effective source snapshot.

        Returns:
            Plan report or focused questions, with invocation telemetry.
        """
        self.logger.info("kind=agent provider=local Planning approved task: title=%r model=%s.", task.proposal.title, self.model)
        started = monotonic()
        prompt = task.model_dump_json(exclude={"proposal": {"process", "routing_process"}})
        try:
            async with asyncio.timeout(self.settings.planner_timeout_seconds):
                async with self.agent:
                    response = await self.agent.run(prompt)
        except asyncio.CancelledError:
            self.logger.warning("Planning cancelled: title=%r elapsed=%.2fs.", task.proposal.title, monotonic() - started)
            raise
        except Exception:
            self.logger.exception("Planning failed: title=%r elapsed=%.2fs.", task.proposal.title, monotonic() - started)
            raise
        output = response.output
        usage = response.usage
        process = ExecutionProcess(
            events=ModelMessagesTypeAdapter.dump_python(response.all_messages(), mode="json"),
            usage={"input_tokens": usage.input_tokens, "cached_input_tokens": usage.cache_read_tokens,
                   "output_tokens": usage.output_tokens, "requests": usage.requests},
        )
        result = TaskResult(content=output.plan.markdown() if output.plan else "\n".join(output.questions),
                            plan=output.plan, questions=output.questions, process=process)
        self.logger.info("Planning completed: title=%r plan_ready=%s questions=%d elapsed=%.2fs.",
                         task.proposal.title, output.plan is not None, len(output.questions), monotonic() - started,
                         extra={"details": {"token_usage": process.usage}})
        return result
