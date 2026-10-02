"""Execute one selected action and store its plan and attributed notes."""

from assistant.protocol.context_store import ContextStoreProtocol
from assistant.protocol.executor import ExecutorProtocol
from assistant.protocol.knowledge import KnowledgePublisherProtocol
from assistant.schemas.execution import WorkRequest, WorkResult
from assistant.schemas.routing import RouterDecision
from assistant.schemas.tracking import WorkRecord


async def execute_action(
    decision: RouterDecision,
    request: WorkRequest,
    script: ExecutorProtocol,
    strong_executor: ExecutorProtocol,
    planner: ExecutorProtocol,
) -> WorkResult:
    action = decision.selected_action_id

    if action == "script":
        result = await script.execute(request)

    elif action == "strong_executor":
        result = await strong_executor.execute(request)

    elif action == "plan":
        # 规划阶段可能需要人工澄清，此时不启动下游执行。
        planning = await planner.execute(request)
        if planning.status == "needs_input":
            return planning

        # 将计划作为任务输入传递，具体研究循环由强处理器内部完成。
        planned_request = request.model_copy(update={"plan": planning.plan})
        result = await strong_executor.execute(planned_request)

        # 保留规划产物，使最终结果能够追溯到执行依据。
        result.plan = planning.plan
        result.knowledge_notes = planning.knowledge_notes + result.knowledge_notes
        result.context_notes = planning.context_notes + result.context_notes

    else:
        result = WorkResult(
            status="needs_input",
            summary="需要澄清目标，尚未执行任务。",
            question="你希望处理哪份材料，得到什么结果？",
        )

    return result


def distribute_result(
    record: WorkRecord,
    context: ContextStoreProtocol,
    knowledge: KnowledgePublisherProtocol,
) -> None:
    """Knowledge is staged as a draft; formal publication is a later approval."""
    result = record.result

    # 草稿写入后回读核对，只有验证成功的回执才进入工作记录。
    for note in result.knowledge_notes:
        receipt = knowledge.publish_draft(note)
        verified = knowledge.read_draft(receipt.id)
        if verified != receipt:
            raise ValueError(f"Draft verification failed: {receipt.id}")

        record.drafts.append(verified)
        record.trace.append(f"knowledge.draft_verified:{receipt.id}")

    # 保存完整结果供后续检索，包括计划和非知识类产物。
    context.remember(record.input, result)
    record.trace.append("context.remember")
