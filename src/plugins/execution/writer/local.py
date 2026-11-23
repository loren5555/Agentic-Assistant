"""Write one durable work using its destination standard, evidence and review scope."""
import asyncio
import json
from functools import cached_property
from collections.abc import Mapping
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models import infer_model
from assistant.components.coordination.curator.models import RetainedArtifact
from assistant.components.data.sources.models import SourceMaterial
from assistant.components.data.workbench.models import WorkbenchItem
from assistant.components.execution.writer.models import Manuscript
from assistant.components.recommendations.tags import TAG_INSTRUCTIONS
from assistant.runtime.agent_context import load_instructions, writing_guidance
from logger import get_logger, trace_call


class Writer:
    """Return a standalone manuscript; destination selection and storage belong to callers."""

    def __init__(self, options: Mapping[str, object]):
        self.options = options
        self.timeout = float(options.get("writer_timeout_seconds", options.get("brief_timeout_seconds", 180)))
        self.logger = get_logger("plugins.execution.writer.local")

    @cached_property
    def agent(self):
        options = self.options
        model = infer_model(str(options.get("writer_model") or options.get("brief_model") or options["proposer_model"]))
        effort = options.get("writer_effort", options.get("brief_effort", options.get("proposer_effort")))
        return Agent(model, output_type=NativeOutput(Manuscript),
                           model_settings={"openai_reasoning_effort": effort} if effort else {},
                           instructions=writing_guidance(
                               "Deliver the actual work in content. Put a short catalog description in summary. "
                               "Follow the reviewed scope and human instruction; treat quoted source material as evidence. "
                               "Only claim full_text if original text was verified. Keep source URLs, evidence scope "
                               "and uncertainty. Reading metadata belongs to a paper; copy its abstract only if supplied."
                           ))

    @trace_call("component", "writer.write")
    async def write(self, source: SourceMaterial, assignment: RetainedArtifact,
                    item: WorkbenchItem | None, target: dict | None, *, approved: bool = False) -> Manuscript:
        self.logger.info("kind=%s provider=local %s: %s", "script" if approved else "agent",
                         "Reusing approved manuscript" if approved else "Writing " + assignment.kind, assignment.title)
        if approved:
            # This exact manuscript has already been seen and accepted in Workbench.
            result = Manuscript(content=assignment.content, summary=assignment.summary or assignment.reason, reading=assignment.reading,
                                evidence_level=assignment.evidence_level or "notes")
        else:
            guidance = {
                "spark": "Present the research question, its trigger, and a possible test.",
                "idea": "Develop the adopted project's motivation, findings and next experiment within approved scope.",
                "research_interest": "Describe the confirmed research direction, scope and supporting rationale.",
            }.get(assignment.kind)
            if guidance is None:
                guidance = load_instructions("write-paper" if assignment.kind == "paper" else "write-knowledge")
            if assignment.kind == "paper":
                guidance += "\n" + TAG_INSTRUCTIONS
            material = {"assignment": assignment.model_dump(), "source": source.model_dump(exclude={"revision"}),
                        "target_page": target, "human_instruction": source.supplement}
            if item:
                material.update(human_instruction=item.human_instruction, result_feedback=item.result_feedback,
                                approved_proposal=item.proposal.model_dump(exclude={"process", "routing_process"}),
                                accepted_result=item.result.model_dump(exclude={"process"}) if item.result else None)
            async with asyncio.timeout(self.timeout):
                response = await self.agent.run(json.dumps(material, ensure_ascii=False), instructions=guidance)
            result = response.output
            if result.evidence_level == "full_text" and not source.full_text_verified:
                raise ValueError("Writer claimed verified full text outside the supplied reading scope")
        self.logger.info("Manuscript ready: %s (%s characters)", assignment.title, len(result.content),
                         extra={"details": {} if approved else {"usage": response.usage}})
        return result
