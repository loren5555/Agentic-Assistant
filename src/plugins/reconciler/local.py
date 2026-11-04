"""Translate review outcomes into source supplements without model calls."""

import json
from assistant.components.inputs.models import SourceHistory, SourceMaterial
from assistant.components.workbench.models import WorkbenchItem
from assistant.components.reconciler.models import Reconciliation
from assistant.runtime.records import digest
from logger import get_logger, trace_call


class TaskReconciler:
    """Own review interpretation while durable steps own storage effects."""

    @trace_call("component", "reconciler.reconcile")
    def reconcile(self, source: SourceMaterial, item: WorkbenchItem) -> Reconciliation:
        """Produce a stable feedback event for an old source version.

        Args:
            source: Scope represented by the previous proposal.
            item: Live human decisions, supplements and prior result.

        Returns:
            A terminal old-work state and optional source feedback.
        """
        logger = get_logger("plugins.reconciler.local")
        logger.info('kind=script provider=local Reconciling human feedback: title=%r review=%s acceptance=%s.',
                    item.title, item.human_review, item.result_review)
        if item.human_review == "Rejected":
            return Reconciliation(status="Deprecated")
        if item.needs_input and not item.human_instruction.strip():
            raise ValueError("Answer the clarification in Human Instruction before submitting it")
        feedback = "\n\n".join(part for part in [item.human_instruction, item.result_feedback] if part)
        if not feedback:
            feedback = "Reconsider this work using the updated source and previous result; obtain clarification when the requested change is unspecified."
        identity = json.dumps([item.page_id, source.version, item.publication_key,
                               item.human_review, item.result_review, feedback], ensure_ascii=False)
        return Reconciliation(status="Superseded", feedback=SourceHistory(
            key=digest(identity), workbench_url=item.url, feedback=feedback,
            result=item.result.model_dump_json(exclude={"process"}) if item.result else "",
            proposal=item.proposal.model_dump_json(exclude={"process", "routing_process"}) if item.proposal else "",
            accepted_plan=item.proposal.execution_plan if item.needs_input and item.proposal else None,
        ))
