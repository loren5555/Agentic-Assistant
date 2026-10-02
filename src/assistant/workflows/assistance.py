"""Route a prepared input and distribute the resulting work."""

from assistant.protocol.context_store import ContextStoreProtocol
from assistant.protocol.executor import ExecutorProtocol
from assistant.protocol.knowledge import KnowledgePublisherProtocol
from assistant.protocol.router import RouterProtocol
from assistant.schemas.execution import WorkRequest
from assistant.schemas.input import WorkInput
from assistant.schemas.routing import ActionCandidate, RouterInput, Trigger
from assistant.schemas.tracking import WorkRecord
from assistant.workflows.execution import distribute_result, execute_action


async def handle_trigger(
    trigger: Trigger,
    input: WorkInput,
    router: RouterProtocol,
    script: ExecutorProtocol,
    strong_executor: ExecutorProtocol,
    planner: ExecutorProtocol,
    context: ContextStoreProtocol,
    knowledge: KnowledgePublisherProtocol,
    records: dict[tuple[str, str], WorkRecord],
) -> WorkRecord:
    # An event may be delivered repeatedly; origins provide independent ID spaces.
    key = (trigger.origin, trigger.event_id)
    if key in records:
        previous = records[key]
        return previous

    # 执行前登记任务，保留重复事件和失败任务的处理依据。
    record = WorkRecord(trigger=trigger, input=input, context=[])
    records[key] = record
    record.trace.append(f"trigger:{trigger.kind}")

    # 候选项描述可执行的能力；Router 不负责生成计划或执行参数。
    candidates = [
        ActionCandidate(
            id="script",
            description="File material or synchronize records through deterministic scripts.",
        ),
        ActionCandidate(
            id="strong_executor",
            description="Organize material, explain questions, or conduct investigations.",
        ),
        ActionCandidate(
            id="plan",
            description="Develop a task plan with steps and expected outcomes.",
        ),
        ActionCandidate(
            id="ask_user",
            description="Obtain necessary information or decisions from the user.",
        ),
    ]

    try:
        # 输入已经由调用端准备；检索失败也保留在本次任务记录中。
        record.trace.append("context.search")
        recalled = context.search(input)
        record.context = recalled
        router_input = RouterInput.from_source(
            input,
            context=recalled,
            candidates=candidates,
        )

        # 决策与执行分开，后续可以替换 Router 而保留执行流程。
        record.decision = await router.decide(router_input)
        record.trace.append(f"router:{record.decision.selected_action_id}")

        request = WorkRequest(input=input, context=recalled)
        record.result = await execute_action(
            record.decision, request, script, strong_executor, planner,
        )
        record.trace.append(f"execution:{record.result.status}")

        # 产物分发成功后，才将任务标记为完成或等待用户输入。
        distribute_result(record, context, knowledge)
        record.status = record.result.status

    except Exception:
        # Worker boundary: preserve the traceback and never automatically replay writes.
        record.status = "failed"
        record.trace.append("failed")
        raise

    return record
