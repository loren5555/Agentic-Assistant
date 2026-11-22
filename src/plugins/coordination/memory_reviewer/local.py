"""Use the project-owned writing skill to revise whole notebooks from feedback.

The model proposes complete text for affected roles. The workflow owns storage,
conflict detection and the durable link to the human decision.
"""
import asyncio
import json
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models import infer_model
from pydantic_ai.models.openai import OpenAIResponsesModelSettings
from assistant.components.data.memory.models import MemoryRevision
from logger import trace_call


class MemoryReviewer:
    def __init__(self, options):
        settings = OpenAIResponsesModelSettings()
        effort = options.get("memory_reviewer_effort", options.get("proposer_effort"))
        if effort:
            settings["openai_reasoning_effort"] = effort
        self.timeout = float(options.get("proposer_timeout_seconds", 180))
        model = options.get("memory_reviewer_model") or options["proposer_model"]
        self.agent = Agent(infer_model(model), model_settings=settings, output_type=NativeOutput(MemoryRevision))

    @trace_call("component", "memory_reviewer.review")
    async def review(self, feedback, earlier, notes, skill):
        prompt = json.dumps({"human_review": feedback.model_dump(), "prior_observations": earlier,
                             "current_notes": {n.role: n.content for n in notes}}, ensure_ascii=False)
        async with asyncio.timeout(self.timeout), self.agent:
            result = await self.agent.run(prompt, instructions=skill)
        return result.output
