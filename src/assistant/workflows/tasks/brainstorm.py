"""Explore one material update or active research question and publish independent proposals.

ResearchLibrary supplies an eligible seed and bounded history. BrainStorm records
findings with evidence, then Proposer reads the report once and chooses which
decisions deserve a Workbench entry. DBOS retains the complete exploration even
when no candidate proceeds. Each proposed decision owns its source, workflow
and human review. Revisions re-enter ordinary intake through propose-tasks.
"""

from __future__ import annotations

from functools import partial
import json

from assistant.runtime.agent_context import use_instructions
from dbos import DBOS

from assistant.components.coordination.brainstorm.models import BrainstormContext, BrainstormMode, ExplorationReport
from assistant.components.coordination.proposer.assessment import CandidateProposal, ReportAssessment
from assistant.components.coordination.proposer.models import Proposal
from assistant.components.data.sources.models import SourceMaterial
from assistant.runtime.records import digest
from assistant.runtime.recovery import invoke
from logger import get_logger, trace_call


logger = get_logger("workflows.tasks.brainstorm")


@DBOS.workflow(name="JobWorkflows.brainstorm")
@trace_call("workflow", "brainstorm")
async def brainstorm(self, mode: BrainstormMode, page_id: str | None = None, exploration_round: str | None = None) -> dict:
    """Choose one starting point and reuse the durable result for that seed revision."""
    context = self.read_brainstorm_context(mode, page_id)
    if context is None:
        reason = (
            "No eligible material in this scan of Papers, Knowledge or Idea research notes."
            if mode == "material" else
            "No eligible active Idea with an open question in this scan."
        )
        logger.info("BrainStorm completed: %s", reason)
        return {"mode": mode, "seed": None, "report": None, "proposals": [], "reason": reason}
    seed_key = [mode, context.seed.page_id, context.seed.revision]
    if exploration_round:
        seed_key.append(exploration_round)
        logger.info("Starting a fresh exploration of %r with current material.", context.seed.title)
    identity = digest(json.dumps(seed_key))
    logger.info("Exploring %r: mode=%s related_records=%d.", context.seed.title, mode, len(context.history))
    return await invoke("brainstorm:" + identity, self.explore_brainstorm, context, identity)


@DBOS.step(name="JobWorkflows.read_brainstorm_context")
@trace_call("step", "read_brainstorm_context")
def read_brainstorm_context(self, mode: BrainstormMode, page_id: str | None) -> BrainstormContext | None:
    lookup = None if page_id else partial(self.services.processor("brainstorm").handled_versions, mode)
    return self.services.research_library.context(mode, page_id, lookup_versions=lookup)


@DBOS.workflow(name="JobWorkflows.explore_brainstorm")
@trace_call("workflow", "explore_brainstorm")
async def explore_brainstorm(self, context: BrainstormContext, identity: str) -> dict:
    """Checkpoint research and assessment before sending decisions to Workbench."""
    report = await self.research_brainstorm(context)
    instructions = None
    if report.candidates:
        snapshot = self.proposals.recall_memory("proposer")
        instructions = snapshot["instructions"]
    assessment = await self.assess_brainstorm(context, report, instructions)
    proposals = []
    for entry in assessment.proposals:
        source = self.stage_brainstorm_candidate(context, identity, report, entry)
        url = await invoke("brainstorm-proposal:" + source.page_id,
                           self.proposals.submit_brainstorm_proposal, source, entry.proposal)
        proposals.append({"candidate_numbers": entry.candidate_numbers, "title": entry.proposal.title, "url": url})
    self.finish_brainstorm(context.mode, context.seed.page_id, context.seed.revision)
    logger.info("Exploration completed: title=%r findings=%d proposals=%d.",
                context.seed.title, len(report.findings), len(proposals))
    return {"mode": context.mode, "seed": context.seed.model_dump(exclude={"text"}),
            "report": report.model_dump(mode="json", exclude={"process"}),
            "assessment": assessment.reason, "proposals": proposals}


@DBOS.step(name="JobWorkflows.research_brainstorm")
@trace_call("step", "research_brainstorm")
async def research_brainstorm(self, context: BrainstormContext) -> ExplorationReport:
    return await self.services.brainstorm.explore(context)


@DBOS.step(name="JobWorkflows.assess_brainstorm")
@trace_call("step", "assess_brainstorm")
async def assess_brainstorm(self, context: BrainstormContext, report: ExplorationReport, instructions: str | None = None) -> ReportAssessment:
    if not report.candidates:
        return ReportAssessment(reason="No candidate items were proposed.", proposals=[])
    with use_instructions(instructions):
        assessment = await self.services.proposer.assess_report(context, report)
    ideas = {n.page_id.replace("-", "").lower() for n in [context.seed, *context.history] if n.collection == "idea"}
    for entry in assessment.proposals:
        if max(entry.candidate_numbers) > len(report.candidates):
            raise ValueError("Proposal references a candidate outside the exploration report")
        artifact = entry.proposal.retention
        if artifact and artifact.target_idea_page_id and artifact.target_idea_page_id.replace("-", "").lower() not in ideas:
            raise ValueError(f"Target Idea of {entry.proposal.title!r} is absent from the research library context")
    return assessment


@DBOS.step(name="JobWorkflows.stage_brainstorm_candidate")
@trace_call("step", "stage_brainstorm_candidate")
def stage_brainstorm_candidate(self, context: BrainstormContext, identity: str,
                              report: ExplorationReport, entry: CandidateProposal) -> SourceMaterial:
    """Give a review decision its own stable source while linking to the real seed."""
    numbers = sorted(entry.candidate_numbers)
    source_id = digest(json.dumps([identity, numbers]))
    candidates = [report.candidates[n - 1] for n in numbers]
    evidence = list(dict.fromkeys(url for candidate in candidates for url in candidate.evidence))
    content = {"seed": context.seed.title, "seed_url": context.seed.url, "summary": report.summary,
               "items": [candidate.model_dump(mode="json") for candidate in candidates],
               "limitations": report.limitations}
    source = SourceMaterial(kind="brainstorm", page_id=source_id, url=context.seed.url, title=entry.proposal.title,
                            text=json.dumps(content, ensure_ascii=False, indent=2), revision=context.seed.revision,
                            metadata={"evidence": evidence, "seed_id": context.seed.page_id, "seed_kind": context.seed.collection,
                                      "report_id": "brainstorm:" + identity, "candidate_numbers": numbers})
    self.services.processor("brainstorm").stage(source)
    return source


@DBOS.workflow(name="ProposalWorkflows.submit_brainstorm_proposal")
@trace_call("workflow", "submit_brainstorm_proposal")
async def submit_brainstorm_proposal(self, source: SourceMaterial, draft: Proposal) -> str:
    """Route and publish the proposal already drafted during the report assessment."""
    logger.info("Submitting BrainStorm proposal for review: title=%r.", draft.title)
    proposal = draft.model_copy(update={"version": source.version, "source_fingerprint": source.fingerprint})
    proposal = await self.select_action(source, proposal)
    item = self.publish_proposal(source, proposal)
    await self.save_checkpoint("proposal:brainstorm:" + source.page_id, source, item)
    self.acknowledge(source)
    logger.info("BrainStorm proposal awaiting review: title=%r.", item.title)
    return item.url


@DBOS.step(name="JobWorkflows.finish_brainstorm")
@trace_call("step", "finish_brainstorm")
def finish_brainstorm(self, mode: BrainstormMode, page_id: str, revision: str) -> None:
    self.services.processor("brainstorm").finish(mode, page_id, revision)
