"""Execute approved proposals using replaceable routing and work capabilities."""

import hashlib

from assistant.actions import INBOX_CANDIDATES
from assistant.protocol.investigator import InvestigatorProtocol
from assistant.protocol.router import RouterProtocol
from assistant.protocol.task import TaskRunnerProtocol, TaskWorkerProtocol
from assistant.protocol.workbench import WorkbenchProtocol
from assistant.schemas.investigation import InvestigationRequest
from assistant.schemas.proposal import ProposedTask, WorkbenchItem
from assistant.schemas.routing import RouterInput
from assistant.schemas.task import ExecutionCycle, TaskResult
from logger import get_logger


class TaskRunner(TaskRunnerProtocol):
    """Own one-at-a-time approved work, routing, and Workbench writeback.

    Attributes:
        workbench: Persistent approval and result storage.
        router: Decision capability selecting a currently executable action.
        worker: Capability completing self-contained tasks and organizing material.
        investigator: Capability consulting public sources when research is needed.
        logger: Execution progress and failure logger.
    """

    def __init__(
        self,
        workbench: WorkbenchProtocol,
        router: RouterProtocol,
        worker: TaskWorkerProtocol,
        investigator: InvestigatorProtocol,
    ) -> None:
        """Bind capabilities without starting work.

        Args:
            workbench: Approval and result storage implementation.
            router: Action-selection implementation.
            worker: Supplied-material task execution implementation.
            investigator: Public-source research implementation.
        """
        self.workbench = workbench
        self.router = router
        self.worker = worker
        self.investigator = investigator
        self.logger = get_logger("providers.local.execution")

    async def run_cycle(self) -> ExecutionCycle:
        """Execute at most one approved task or human-requested redo.

        Returns:
            Result links, clarification links, and actual execution failures.
        """
        cycle = ExecutionCycle()
        items = self.workbench.list_items(statuses=["Open", "Executed"])
        for listed_item in items:
            if not self._eligible(listed_item):
                continue

            # Re-read human decisions before spending resources on this task.
            item = self.workbench.read_item(listed_item.page_id)
            if not self._eligible(item):
                continue
            try:
                await self._execute(item, cycle)
            except Exception as error:
                # This is the execution recovery boundary, not a fallback result.
                self.logger.exception("Approved task failed: %s", item.url)
                detail = f"{type(error).__name__}: {error}"
                self.workbench.save_error(item, detail)
                cycle.failed[item.url] = detail
            break
        return cycle

    def _eligible(self, item: WorkbenchItem) -> bool:
        """Identify explicit approval or a human-requested redo.

        Args:
            item: Current stored proposal and human review states.

        Returns:
            Whether this managed proposal is currently authorized to execute.
        """
        approved = item.status == "Open" and item.human_review == "Approved"
        redo = item.status == "Executed" and item.result_review == "Unqualified"
        eligible = item.proposal is not None and (approved or redo)
        return eligible

    async def _execute(self, item: WorkbenchItem, cycle: ExecutionCycle) -> None:
        """Route approved scope and write its deliverable to the same page.

        Args:
            item: Eligible proposal with current human decisions.
            cycle: Summary receiving this task's outcome.
        """
        proposal = item.proposal
        if proposal is None:
            return
        source = self.workbench.read_source(item.source_url)
        digest = hashlib.sha256(source.text.encode()).hexdigest()
        if digest != proposal.source_fingerprint:
            # Proposer will revise changed material before it can be executed.
            return

        redo = item.status == "Executed"
        feedback = [item.human_instruction]
        if redo:
            feedback.append(item.result_feedback)
        instruction = "\n\n".join(text for text in feedback if text)
        task = ProposedTask(
            workbench_url=item.url,
            proposal=proposal,
            instruction=instruction,
            redo=redo,
        )
        context = [f"Original material:\n{source.text}"]
        if redo and item.result is not None:
            context.append(f"Previous result to correct:\n{item.result.content}")
        request = RouterInput(
            text=task.model_dump_json(exclude={"proposal": {"process"}}),
            context=context,
            candidates=INBOX_CANDIDATES,
        )
        self.logger.info("Routing approved task: %s.", proposal.title)
        decision = await self.router.decide(request)
        action = decision.selected_action_id

        if action == "ask_user":
            question = decision.clarification_question or decision.suggested_next_step
            self.workbench.request_input(item, question)
            cycle.needs_input.append(item.url)
            return

        if action == "investigate_question":
            report = await self.investigator.investigate(
                InvestigationRequest(question=request.text, context=context),
            )
            sections = [report.answer]
            if report.sources:
                sections.append("## Sources\n" + "\n".join(
                    f"- [{source.title}]({source.url}): {source.finding}"
                    for source in report.sources
                ))
            if report.limitations:
                sections.append("## Limitations\n" + "\n".join(report.limitations))
            result = TaskResult(content="\n\n".join(sections), process=report.process)
        elif action in {"complete_task", "organize_material"}:
            # Original material and previous output are also needed by the worker.
            task.instruction = "\n\n".join([instruction, *context])
            result = await self.worker.execute(task)
        else:
            raise ValueError(f"No execution handler for action: {action}")

        result.action_id = action
        # Do not commit against an approval or scope edited while models were running.
        current = self.workbench.read_item(item.page_id)
        if (
            not self._eligible(current)
            or current.proposal is None
            or current.proposal.model_dump(exclude={"process"}) != proposal.model_dump(exclude={"process"})
            or current.human_instruction != item.human_instruction
            or current.result_feedback != item.result_feedback
        ):
            raise RuntimeError("Proposal or human review changed during execution; result was not committed")

        self.workbench.save_result(item, result)
        cycle.executed.append(item.url)
