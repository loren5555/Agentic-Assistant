"""Project saved DBOS executions into tasks, component actions and reading outcomes.

Only deserialize values read from the local DBOS database. The business report
uses selected domain fields. Historical telemetry is attributed to the step
that produced it, never to later snapshots that copied the result.
"""
from contextlib import closing
import json
import re

from assistant.runtime.serialization import ComponentSerializer
from .metadata import JOB_LABELS, label
from .presentation import error_message

# Only operations with a user-visible purpose enter the activity timeline.
STEPS = {
    "read_brainstorm_context": ("选择研究起点与历史材料", "研究资料库"),
    "research_brainstorm": ("探索材料之间的联系", "BrainStorm"),
    "assess_brainstorm": ("从报告中选取独立提案", "Proposer"),
    "stage_brainstorm_candidate": ("保留待审批的条目", "研究报告"),

    "read_sources": ("读取待处理条目", "来源处理器"),
    "brief_source": ("摘要来源材料", "Source Briefer"),
    "publish_source_brief": ("归档来源摘要", "Information Publisher"),
    "organize_source": ("整理来源材料", "Information Organizer"),
    "draft": ("起草提案", "Proposer"), "select_action": ("选择执行方式", "Router"),
    "decide": ("选择执行方式", "Router"), "publish_proposal": ("提交提案", "Workbench"),
    "read_review": ("读取人工审批", "Workbench"), "read_source": ("读取任务来源", "来源处理器"),
    "execute": ("执行已批准的任务", "执行器"), "save_result": ("保存执行结果", "Workbench"),
    "extract": ("提取值得保留的成果", "Curator"), "publish_artifact": ("归档成果", "信息发布器"),
    "acknowledge": ("标记来源已处理", "来源处理器"), "request_input": ("请求补充信息", "Workbench"),
    "accept_plan": ("采纳执行计划", "Workbench"), "close_item": ("结束条目处理", "Workbench"),
    "apply_reconciliation": ("处理反馈并更新来源", "Reconciler"), "save_error": ("记录执行错误", "Workbench"),
    "read_preferences": ("读取推荐方向", "Recommendation Tags"), "read_interests": ("读取研究兴趣", "Research Interests"),
    "collection_brief": ("确定本次检索重点", "Collector"), "collect": ("收集研究候选", "Collector"),
    "discover": ("搜索研究候选", "Discovery"), "prepare_pool_display": ("整理候选与研究方向", "Recommender"),
    "refresh_pool": ("更新发现池", "Discovery Pool"), "rank": ("选择精读候选", "Recommender"),
    "read": ("阅读研究证据", "Evidence Reader"), "assess": ("评估推荐价值", "Recommender"),
    "publish": ("发布每日推荐", "Research Feed"), "save_directions": ("保存后续检索方向", "Collector"),
}
TRACE_FIELDS = {
    "research_brainstorm": "process", "assess_brainstorm": "process",
    "draft": "process", "execute": "process", "decide": "process", "select_action": "routing_process",
    "read": "process", "assess": "process", "discover": "process", "collect": "process",
}
EXECUTORS = {"run_experiment": "Codex 实验执行", "investigate_literature": "AMiner 沉思", "investigate_question": "Investigator", "plan": "Planner", "complete_task": "Task Worker",
             "propose_direction": "Direction Proposer", "organize_material": "材料整理执行器"}
FIELDS = {
    "title": "条目", "text": "原始内容", "human_review": "审批", "human_instruction": "人工说明",
    "result_review": "验收", "result_feedback": "验收反馈", "status": "条目状态", "purpose": "目的",
    "action": "任务", "plan": "计划", "questions": "待确认问题", "content": "内容", "expected_result": "预期成果",
    "selected_action_id": "执行方式", "user_intent": "意图", "summary": "摘要", "reason": "依据",
    "notes": "说明", "answer": "回答", "url": "页面", "understanding": "材料解读", "key_points": "要点",
    "findings": "研究发现", "limitations": "局限", "claim": "线索", "next_step": "建议",
    "qualified": "通过筛选", "category": "栏目", "day": "日期", "job": "任务",
}
OPAQUE = re.compile(r"^(?:[\w-]+:)?[\da-f-]{32,}$|^gAS[A-Za-z0-9+/=]{16,}$", re.I)


def short_name(name):
    return re.sub(r"\.v\d+$", "", name or "").rsplit(".", 1)[-1]


def unpack(raw, encoding):
    if raw is None:
        return None
    try:
        if encoding in (None, "py_pickle"):
            return ComponentSerializer().deserialize(raw)
        if encoding == "portable_json":
            return json.loads(raw)
    except Exception:
        pass
    return Unreadable()


class Unreadable:
    """A stored output that this version cannot interpret."""


def values(obj):
    return obj if isinstance(obj, dict) else getattr(obj, "__dict__", {})


def clean(value):
    if not isinstance(value, str) or OPAQUE.fullmatch(value.strip()):
        return ""
    return value.strip()[:8000]


def describe(value):
    """Return readable lines only; storage keys and provider envelopes stay internal."""
    if isinstance(value, Unreadable):
        return ["此版本无法读取该历史结果。"]
    if isinstance(value, BaseException):
        return [clean(str(value)) or "执行出错"]
    if isinstance(value, str):
        s = clean(value)
        return [JOB_LABELS.get(s, s)] if s else []
    if isinstance(value, (tuple, list)):
        lines = [f"共 {len(value)} 项"]
        for item in value[:12]:
            title = clean(values(item).get("title")) or clean(item)
            if title:
                lines.append(JOB_LABELS.get(title, title))
        return lines
    obj = values(value)
    lines = []
    for key, caption in FIELDS.items():
        v = obj.get(key)
        if isinstance(v, list):
            v = "、".join(filter(None, (clean(x) for x in v[:12])))
        elif isinstance(v, bool):
            v = "是" if v else "否"
        if clean(v):
            lines.append(f"{caption}：{JOB_LABELS.get(v, v)[:8000]}")
    if "report" in obj and "proposals" in obj:
        if not obj.get("seed"):
            return ["本次未找到待探索的研究材料。"]
        lines.extend(describe(values(obj["seed"]).get("title")))
        lines.extend(describe(obj["report"]))
        if reason := clean(obj.get("assessment")):
            lines.append("提案筛选：" + reason)
        for proposal in obj["proposals"]:
            entry = values(proposal)
            if title := clean(entry.get("title")):
                lines.append("提案：" + title)
                if url := clean(entry.get("url")):
                    lines.append(url)
    if "findings" in obj and "candidates" in obj:
        for candidate in obj["candidates"]:
            entry = values(candidate)
            lines.extend(describe(entry))
            lines.extend(url for url in entry.get("evidence", []) if clean(url))
    for key, caption in (("candidates","候选"), ("published","已发布"), ("selected","入选"), ("artifacts","保留成果")):
        if isinstance(obj.get(key), list):
            lines.append(f"{caption}：{len(obj[key])} 项")
    return lines


def call_data(step, obj, role):
    field = TRACE_FIELDS.get(step)
    trace = values(obj.get(field)) if field else {}
    if step == "collect" and not trace:
        trace = values(values(obj.get("discovery")).get("process"))
    if not (trace.get("events") or trace.get("usage")):
        return None
    provider = clean(trace.get("provider"))
    model = clean(trace.get("model"))
    tools, prompts = [], []
    for event in trace.get("events", []):
        provider = clean(event.get("provider_name")) or provider
        if not provider:
            if event.get("type") == "aminer.deep_research.completed":
                provider = "AMiner"
            elif event.get("type") in {"thread.started", "turn.completed"}:
                provider = "Codex"
        model = clean(event.get("model_name")) or model
        for part in event.get("parts", []):
            if part.get("part_kind") == "user-prompt" and isinstance(part.get("content"), str):
                content = part["content"]
                try:
                    payload = json.loads(content)
                except ValueError:
                    prompts.extend(describe(content))
                else:
                    prompts.extend(describe(payload))
                    for key in ("source", "proposal", "candidate", "task", "input", "instruction"):
                        prompts.extend(describe(values(payload).get(key)))
            if part.get("part_kind") == "tool-call" and clean(part.get("tool_name")):
                tools.append(part["tool_name"])
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") in {"web_search","mcp_tool_call","command_execution"}:
            tools.append(item.get("tool") or item["type"])
    usage = trace.get("usage") or {}
    return {"module": role, "provider": provider, "model": model, "tools": tools, "input": list(dict.fromkeys(prompts))[:12],
            "tokens_in": usage.get("input_tokens"), "tokens_out": usage.get("output_tokens")}


def describe_error(raw, encoding):
    value = unpack(raw, encoding)
    if isinstance(value, Unreadable):
        if encoding in (None, "py_pickle") and isinstance(raw, str) and raw.startswith("gAS"):
            return [error_message(raw, "无法读取已保存的异常详情")]
        return ["无法读取已保存的异常详情，请查看服务日志。"]
    return describe(value)


def business_step(row):
    name = short_name(row["function_name"])
    if name not in STEPS:
        return None
    title, module = STEPS[name]
    value = unpack(row["output"],row["serialization"])
    obj = values(value)
    if name == "execute":
        module = EXECUTORS.get(obj.get("action_id"), module)
    lines = describe(value)
    if name == "save_result":
        result = obj.get("result")
        if values(result).get("delivery_source") == "external":
            title = "接收外部交付成果"
            lines.append("交付来源：外部提交")
        lines += describe(result)
    if name == "organize_source" and isinstance(obj.get("organization"), str):
        try:
            lines = describe(json.loads(obj["organization"])) or lines
        except ValueError:
            pass
    error = describe_error(row["error"], row["serialization"])
    subject = clean(obj.get("title"))
    if name == "read_sources" and isinstance(value, (list, tuple)) and len(value) == 1:
        subject = clean(values(value[0]).get("title"))
    return {"number": row["function_id"], "action": title, "module": module, "subject": subject,
            "result": lines, "error": error, "call": call_data(name, obj, module)}


def workflow_args(raw, encoding):
    inputs = values(unpack(raw, encoding))
    return [*inputs.get("args", inputs.get("positionalArgs", [])),
            *inputs.get("kwargs", inputs.get("namedArgs", {})).values()]


def item_titles(db, workflow_id):
    row = db.execute("""SELECT w.serialization,coalesce(i.inputs,w.inputs) AS inputs
        FROM workflow_status w LEFT JOIN workflow_input i USING(workflow_uuid)
        WHERE workflow_uuid=?""", (workflow_id,)).fetchone()
    source = item = ""
    for arg in workflow_args(row["inputs"], row["serialization"]):
        obj = values(arg)
        # Review workflows store source and item together in a state snapshot.
        if "source" in obj and "item" in obj:
            source = clean(values(obj["source"]).get("title"))
            item = clean(values(obj["item"]).get("title"))
        elif "kind" in obj and "page_id" in obj:
            source = clean(obj.get("title"))
        elif "human_review" in obj:
            item = clean(obj.get("title"))
    return source, item


def activity(metadata, workflow_id):
    run = metadata.get(workflow_id)
    if not run:
        return None
    with closing(metadata.connect()) as db:
        row = db.execute("""SELECT w.serialization,coalesce(i.inputs,w.inputs) AS inputs,
            coalesce(o.output,w.output) AS output,coalesce(o.error,w.error) AS error FROM workflow_status w
            LEFT JOIN workflow_input i USING(workflow_uuid) LEFT JOIN workflow_output o USING(workflow_uuid)
            WHERE workflow_uuid=?""",(workflow_id,)).fetchone()
        # Follow child-workflow references as well as parent IDs. Reused durable
        # operations can be referenced by more than one dispatch.
        operations = [f"{owner}.{name}{suffix}" for owner in
                      ("JobWorkflows", "ProposalWorkflows", "ResearchWorkflows")
                      for name in STEPS for suffix in ("", ".v2")]
        marks = ",".join("?" for _ in operations)
        rows = db.execute(f"""WITH RECURSIVE family(id) AS (
            SELECT ? UNION SELECT w.workflow_uuid FROM workflow_status w JOIN family f ON w.parent_workflow_id=f.id
            WHERE w.application_name='assistant' OR w.application_name IS NULL
            UNION SELECT o.child_workflow_id FROM operation_outputs o JOIN family f ON o.workflow_uuid=f.id
            JOIN workflow_status w ON w.workflow_uuid=o.child_workflow_id
            WHERE w.application_name='assistant' OR w.application_name IS NULL
        ) SELECT o.*, w.name AS workflow_name FROM operation_outputs o JOIN family f ON f.id=o.workflow_uuid
          JOIN workflow_status w ON w.workflow_uuid=f.id
          WHERE o.function_name IN ({marks}) ORDER BY o.started_at_epoch_ms,o.rowid LIMIT 121""",
                          [workflow_id,*operations]).fetchall()
        steps = []
        titles = {}
        for stored in rows[:120]:
            step = business_step(stored)
            owner = step["workflow"] = stored["workflow_uuid"]
            name = short_name(stored["function_name"])
            source_step = name in {"organize_source", "brief_source", "publish_source_brief", "acknowledge", "read_source"}
            if stored["workflow_name"].startswith("ProposalWorkflows.") and (source_step or not step["subject"]):
                if owner not in titles:
                    titles[owner] = item_titles(db, owner)
                source, item = titles[owner]
                if source_step:
                    step["subject"] = source or step["subject"]
                else:
                    step["subject"] = item or source
            steps.append(step)
    args = workflow_args(row["inputs"], row["serialization"])
    subject = next((clean(values(a).get("title")) for a in args if clean(values(a).get("title"))), "")
    subject = subject or next((step["subject"] for step in steps if step["subject"]), "")
    if short_name(run["name"]) == "dispatch" and args and isinstance(args[0], str):
        run["title"] = JOB_LABELS.get(args[0], run["title"])
    errors = describe_error(row["error"], row["serialization"])
    if run["status"] == "ERROR":
        failed = next((step for step in reversed(steps) if step["error"]), None)
        if failed:
            reason = f"{failed['module']} · {failed['action']}：{'；'.join(failed['error'])}"
            errors = [reason, *(line for line in errors if line not in failed["error"])]
    refs = metadata.references(workflow_id)
    return {"run": run, "subject": subject if all(step["workflow"] == workflow_id for step in steps) else "",
            "more_steps": len(rows) > 120, "input": [line for a in args for line in describe(a)],
            "result": describe(unpack(row["output"],row["serialization"])),
            "error": errors, "steps": steps,
            "parents": refs["parents"], "children": refs["children"]}


def calls_page(metadata, before):
    # Only inspect telemetry-producing steps. Page through bounded batches, also
    # when an earlier provider stored no trace for an otherwise eligible step.
    names = [f"{prefix}.{step}{suffix}" for prefix in ("JobWorkflows","ProposalWorkflows","ResearchWorkflows")
             for step in TRACE_FIELDS for suffix in ("", ".v2")]
    placeholders = ",".join("?" for _ in names)
    with closing(metadata.connect()) as db:
        rows = db.execute(f"""SELECT o.rowid AS cursor,o.*,w.name,w.attributes FROM operation_outputs o
            JOIN workflow_status w USING(workflow_uuid) WHERE (w.application_name='assistant' OR w.application_name IS NULL)
            AND o.rowid < ? AND o.function_name IN ({placeholders}) ORDER BY o.rowid DESC LIMIT 41""",
            [before,*names]).fetchall()
        calls = []
        for row in rows[:40]:
            step = business_step(row)
            if not step or not step["call"]:
                continue
            task = step["subject"] or (json.loads(row["attributes"] or "{}") or {}).get("title")
            if not task:
                context = db.execute("""SELECT serialization,output FROM operation_outputs
                    WHERE workflow_uuid=? AND function_id<? AND function_name IN
                    ('ProposalWorkflows.read_review','ProposalWorkflows.organize_source','ProposalWorkflows.draft')
                    ORDER BY function_id DESC LIMIT 1""", (row["workflow_uuid"],row["function_id"])).fetchone()
                if context:
                    task = clean(values(unpack(context["output"],context["serialization"])).get("title"))
            calls.append({"workflow": row["workflow_uuid"], "task": task or label(row["name"], {}),
                          "time": row["started_at_epoch_ms"], **step})
    return {"calls": calls,"next": rows[39]["cursor"] if len(rows)>40 else None}
