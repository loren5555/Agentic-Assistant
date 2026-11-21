"""Apply explicit browser maintenance requests through DBOS public APIs.

Input: selected execution IDs and a reviewed deletion preview. Output: per-run
receipts. Active business references and shared successful discovery checkpoints
are retained. Deletion affects execution records only, never Notion or WorkIndex.
"""

import asyncio
import hashlib
import json
from typing import Annotated

from dbos import DBOS
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException
from starlette.routing import Route

from logger import get_logger
from .models import TERMINAL_STATES

logger = get_logger("runtime.service.administration")


class Selection(BaseModel):
    """Bound each maintenance request to an explicit nonempty selection."""

    model_config = ConfigDict(extra="forbid")
    ids: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=512)]],
        Field(min_length=1, max_length=50),
    ]


class Deletion(Selection):
    """Require the exact preview snapshot before applying a deletion."""

    token: str = Field(min_length=64, max_length=64)


def preview(metadata, ids):
    """Resolve dependencies and retain records referenced by retained parents."""
    items = []
    for workflow_id in dict.fromkeys(ids):
        run = metadata.get(workflow_id)
        if run is None:
            items.append(
                {
                    "id": workflow_id,
                    "title": workflow_id,
                    "status": "MISSING",
                    "allowed": False,
                    "reasons": ["记录已不存在"],
                    "references": {},
                }
            )
            continue
        refs = metadata.references(workflow_id)
        reasons = []
        if run["status"] not in TERMINAL_STATES:
            reasons.append("任务尚未结束，请先取消并等待当前调用结束")
        if refs["partial"]:
            reasons.append("关联记录超过预览上限，保留该记录")
        if refs["business"]:
            reasons.append("仍被未完成的 Workbench 工作引用")
        if any(child["status"] not in TERMINAL_STATES for child in refs["children"]):
            reasons.append("仍有未结束的子任务")
        if run["status"] == "SUCCESS" and workflow_id.startswith(
            ("collection:", "edition:", "recommendations:")
        ):
            reasons.append("共享的推荐缓存检查点，保留以维持去重与复用")
        items.append(
            {**run, "references": refs, "allowed": not reasons, "reasons": reasons}
        )
    changed = True
    while changed:
        changed = False
        allowed = {item["id"] for item in items if item["allowed"]}
        for item in items:
            if item["allowed"] and any(
                p["id"] not in allowed for p in item["references"]["parents"]
            ):
                item["allowed"] = False
                item["reasons"].append("仍被保留的父任务或检查点引用")
                changed = True
    # Only stable identity/state/reference data enter the confirmation token.
    snapshot = [
        {
            key: item.get(key)
            for key in (
                "id",
                "status",
                "updated_at",
                "allowed",
                "reasons",
                "references",
            )
        }
        for item in items
    ]
    token = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return {
        "items": items,
        "token": token,
        "scope": "selected_records_only",
        "allowed_count": sum(item["allowed"] for item in items),
    }


def routes(metadata, respond, lock):
    """Serialize administration with manual submission/recovery requests."""

    async def inspect_deletion(request):
        selected = Selection.model_validate(await request.json())
        logger.debug(
            "Preparing execution deletion preview: selected=%d.", len(selected.ids)
        )
        result = await asyncio.to_thread(preview, metadata, selected.ids)
        logger.debug(
            "Execution deletion preview prepared: allowed=%d retained=%d.",
            result["allowed_count"],
            len(result["items"]) - result["allowed_count"],
        )
        return respond(result)

    async def delete(request):
        selected = Deletion.model_validate(await request.json())
        async with lock:
            current = await asyncio.to_thread(preview, metadata, selected.ids)
            if current["token"] != selected.token:
                raise HTTPException(409, "记录状态或引用已变化，请重新预览")
            pending = {item["id"]: item for item in current["items"] if item["allowed"]}
            results = [
                {"id": item["id"], "status": "retained", "reasons": item["reasons"]}
                for item in current["items"]
                if not item["allowed"]
            ]
            # Parents first, so each next deletion can be checked again against
            # the references that actually remain after earlier writes.
            while pending:
                ready = [
                    item
                    for item in pending.values()
                    if not any(
                        parent["id"] in pending
                        for parent in item["references"]["parents"]
                    )
                ]
                if not ready:
                    results.extend(
                        {
                            "id": key,
                            "status": "retained",
                            "reasons": ["关联存在循环，保留记录"],
                        }
                        for key in pending
                    )
                    break
                for item in ready:
                    workflow_id = item["id"]
                    del pending[workflow_id]
                    fresh = await asyncio.to_thread(preview, metadata, [workflow_id])
                    if not fresh["items"][0]["allowed"]:
                        results.append(
                            {
                                "id": workflow_id,
                                "status": "retained",
                                "reasons": fresh["items"][0]["reasons"],
                            }
                        )
                        continue
                    logger.info("Deleting saved execution: title=%r.", item["title"])
                    try:
                        await DBOS.delete_workflow_async(
                            workflow_id, delete_children=False
                        )
                        if await asyncio.to_thread(metadata.get, workflow_id):
                            raise RuntimeError(
                                "Deletion readback found the execution still present"
                            )
                    except Exception as error:
                        logger.exception(
                            "Execution deletion failed: title=%r.", item["title"]
                        )
                        results.append(
                            {"id": workflow_id, "status": "failed", "error": str(error)}
                        )
                    else:
                        logger.info("Saved execution deleted: title=%r.", item["title"])
                        results.append({"id": workflow_id, "status": "deleted"})
            return respond({"items": results})

    async def cancel(request):
        workflow_id = request.path_params["workflow_id"]
        async with lock:
            run = await asyncio.to_thread(metadata.get, workflow_id)
            if not run:
                raise HTTPException(404, "Workflow not found")
            if run["status"] not in TERMINAL_STATES:
                logger.info("Cancelling execution: title=%r.", run["title"])
                await DBOS.cancel_workflow_async(workflow_id, cancel_children=False)
                logger.info("Execution cancellation recorded: title=%r.", run["title"])
            return respond(
                {
                    "id": workflow_id,
                    "status": (await asyncio.to_thread(metadata.get, workflow_id))[
                        "status"
                    ],
                    "scope": "selected_record_only",
                    "note": "正在进行的外部调用可能继续到返回；子任务不会自动取消。",
                }
            )

    return [
        Route("/panel/delete-preview", inspect_deletion, methods=["POST"]),
        Route("/panel/delete", delete, methods=["POST"]),
        Route("/panel/runs/{workflow_id}/cancel", cancel, methods=["POST"]),
    ]
