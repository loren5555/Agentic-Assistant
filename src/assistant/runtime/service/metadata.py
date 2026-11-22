"""Read paginated execution metadata without deserializing checkpoint payloads.

Input origin: validated panel filters and configured local SQLite paths.
Output destination: run summaries, counts and deletion-reference previews.
DBOS remains the only writer to its system tables. These bounded read-only queries
are isolated here because the SDK list API lacks substring search and count queries.
"""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time
from urllib.parse import quote
from typing import Literal

from .models import TERMINAL_STATES

from pydantic import BaseModel, ConfigDict, Field

JOB_LABELS = {
    "brainstorm-material": "从研究笔记探索线索",
    "brainstorm-idea": "探索在研 Idea 的问题",
    "propose-tasks": "整理 Inbox / TODO",
    "organize-papers": "整理论文",
    "organize-articles": "整理剪辑",
    "process-signals": "处理阅读跟进",
    "reconcile-feedback": "处理人类反馈",
    "process-workbench": "处理 Workbench",
    "recommend-papers": "每日研究推荐",
    "recommend-papers-deep": "每周深度推荐",
    "recommend-papers-light": "每日轻量推荐",
}
PHASE_LABELS = {
    **{key.replace("-", "_"): value for key, value in JOB_LABELS.items()},
    "dispatch": "运行工作流", "review_memory": "复盘反馈与更新记忆", "intake_item": "整理来源条目", "reconcile_item": "处理条目反馈",
    "brainstorm": "整理研究线索", "explore_brainstorm": "生成探索报告",
    "submit_brainstorm_proposal": "提交研究提案",
    "daily_newspaper": "生成研究日报",
    "collect_research": "收集研究候选",
    "recommendations": "筛选研究推荐",
    "submit_proposal": "提交提案",
    "review_item": "处理提案",
    "receive_delivery": "接收外部交付成果",
    "intake_sources": "整理输入来源",
    "scheduled_job": "定时触发",
    "recover_requested_workflow": "恢复执行",
    "draft": "起草提案",
    "execute": "执行已批准任务",
    "publish": "发布结果",
    "read": "读取研究证据",
    "assess": "评估候选",
    "rank": "排序候选",
}
STATES = {
    "PENDING",
    "ENQUEUED",
    "DELAYED",
    "SUCCESS",
    "ERROR",
    "CANCELLED",
    "MAX_RECOVERY_ATTEMPTS_EXCEEDED",
}


# Resolve business names before filtering and pagination, including older recovery
# wrappers whose only link to the original work is a saved DBOS.getResult step.
RUNS = """
WITH runs AS (
    SELECT w.*,
      COALESCE(json_extract(w.attributes,'$.job'),
        CASE w.name
          WHEN 'scheduled_job' THEN COALESCE(
            CASE WHEN w.schedule_name LIKE 'assistant-%' THEN substr(w.schedule_name,11) END,
            (SELECT json_extract(c.attributes,'$.job') FROM workflow_status c
             WHERE c.parent_workflow_id=w.workflow_uuid AND c.name='JobWorkflows.dispatch' LIMIT 1))
          WHEN 'recover_requested_workflow' THEN (
            WITH RECURSIVE lineage(id) AS (
                SELECT COALESCE(json_extract(w.attributes,'$.target_id'),
                    (SELECT o.child_workflow_id FROM operation_outputs o
                     WHERE o.workflow_uuid=w.workflow_uuid AND o.function_name='DBOS.getResult'
                       AND o.child_workflow_id IS NOT NULL ORDER BY o.function_id DESC LIMIT 1))
                UNION SELECT a.parent_workflow_id FROM workflow_status a JOIN lineage ON a.workflow_uuid=lineage.id
            )
            SELECT COALESCE(json_extract(t.attributes,'$.job'), substr(t.schedule_name,11))
            FROM workflow_status t JOIN lineage ON t.workflow_uuid=lineage.id
            WHERE json_extract(t.attributes,'$.job') IS NOT NULL OR t.schedule_name LIKE 'assistant-%'
            LIMIT 1)
        END) AS business_job
    FROM workflow_status w
)
"""


class RunFilters(BaseModel):
    """Bound metadata queries independently from any execution request."""

    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    scope: str = "roots"
    status: str = ""
    job: str = ""
    search: str = Field(default="", max_length=200)
    since: str = "7d"
    queue: str = ""
    archive: Literal["current", "archived", "all"] = "current"


def label(name: str, attributes: dict) -> str:
    """Prefer stored business titles, then readable job/phase names."""
    title = attributes.get("title")
    if isinstance(title, str) and title.strip():
        return title[:180]
    job = attributes.get("job")
    if job in JOB_LABELS:
        return JOB_LABELS[job]
    parts = name.split(".")
    phase = parts[-2] if len(parts) > 1 and parts[-1].startswith("v") and parts[-1][1:].isdigit() else parts[-1]
    return PHASE_LABELS.get(phase, "其他工作流")


def summarize(row: dict) -> dict:
    """Convert metadata into a lightweight browser row without raw payloads."""
    attributes = json.loads(row.get("attributes") or "{}") or {}
    started = row.get("started_at_epoch_ms")
    if started is None and row["status"] not in {"ENQUEUED", "DELAYED", "CANCELLED"}:
        started = row["created_at"]
    end = row.get("completed_at") or int(time.time() * 1000)
    job = row.get("business_job") or attributes.get("job")
    trigger = None
    if row["name"] == "scheduled_job":
        trigger = "定时"
    elif row["name"] == "recover_requested_workflow":
        trigger = "恢复"
    elif row["name"] == "JobWorkflows.dispatch" and row["workflow_uuid"].startswith("manual:"):
        trigger = "手动"
    name = row.get("dispatched") or row["name"]
    return {
        "id": row["workflow_uuid"],
        "name": row["name"],
        "title": label(name, {**attributes, "job": job}),
        "trigger": trigger,
        "job": job,
        "status": row["status"],
        "parent_id": row.get("parent_workflow_id"),
        "queue": row.get("queue_name"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": started,
        "completed_at": row.get("completed_at"),
        "duration_ms": max(0, end - started) if started else None,
        "application_version": row.get("application_version"),
        "step_count": row.get("step_count", 0),
        "attributes": attributes,
    }


class RunMetadata:
    """Own read-only system metadata queries for one local Assistant runtime."""

    def __init__(self, directory: str) -> None:
        """Bind paths without opening a database or launching DBOS."""
        self.directory = Path(directory).resolve() / "v2"
        self.path = self.directory / "dbos.sqlite"

    def connect(self, path: Path | None = None):
        """Open a query-only SQLite connection, including the live WAL snapshot."""
        path = path or self.path
        connection = sqlite3.connect(
            "file:" + quote(str(path)) + "?mode=ro", uri=True, timeout=5
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection

    def panel_connection(self):
        """Store visibility in the panel database and read DBOS through a read-only attachment."""
        connection = sqlite3.connect(self.directory.joinpath("panel.sqlite").as_uri(), uri=True)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("CREATE TABLE IF NOT EXISTS archived_runs "
                               "(id TEXT PRIMARY KEY, created_at INTEGER, updated_at INTEGER)")
            connection.execute("ATTACH DATABASE ? AS history", (self.path.as_uri() + "?mode=ro",))
        except Exception:
            connection.close()
            raise
        return connection

    def change_archive(self, ids, archived):
        """Apply a reversible visibility change to the selected finished executions."""
        handled = []
        with closing(self.panel_connection()) as connection, connection:
            for run_id in dict.fromkeys(ids):
                row = connection.execute(
                    "SELECT created_at, updated_at, status FROM history.workflow_status WHERE workflow_uuid=? "
                    "AND (application_name='assistant' OR application_name IS NULL)", (run_id,)
                ).fetchone()
                if not row or row["status"] not in TERMINAL_STATES:
                    continue
                if archived:
                    connection.execute("INSERT OR REPLACE INTO archived_runs VALUES (?, ?, ?)",
                                       (run_id, row["created_at"], row["updated_at"]))
                else:
                    connection.execute("DELETE FROM archived_runs WHERE id=?", (run_id,))
                handled.append(run_id)
        return handled

    def _where(self, filters: RunFilters, include_status=True):
        """Build parameterized filter predicates; overview ignores only state."""
        conditions = [
            "(w.application_name = 'assistant' OR w.application_name IS NULL)"
        ]
        values = []
        if filters.archive != "all":
            archived = ("EXISTS (SELECT 1 FROM archived_runs a WHERE a.id=w.workflow_uuid "
                        "AND a.created_at=w.created_at AND a.updated_at=w.updated_at)")
            conditions.append(archived if filters.archive == "archived" else "NOT " + archived)
        if filters.scope not in {"roots", "all"}:
            raise ValueError("scope must be roots or all")
        if filters.scope == "roots":
            conditions.append(
                "(w.parent_workflow_id IS NULL OR NOT EXISTS (SELECT 1 FROM workflow_status p WHERE p.workflow_uuid=w.parent_workflow_id))"
            )
        if filters.status and include_status:
            if filters.status == "FAILED":
                conditions.append(
                    "w.status IN ('ERROR','MAX_RECOVERY_ATTEMPTS_EXCEEDED')"
                )
            elif filters.status in STATES:
                conditions.append("w.status=?")
                values.append(filters.status)
            else:
                raise ValueError("Unknown workflow status")
        if filters.job:
            conditions.append("w.business_job=?")
            values.append(filters.job)
        if filters.queue:
            conditions.append("w.queue_name=?")
            values.append(filters.queue)
        if filters.search:
            search = (
                "%"
                + filters.search.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
                + "%"
            )
            matches = [
                "w.workflow_uuid LIKE ? ESCAPE '\\'",
                "w.name LIKE ? ESCAPE '\\'",
                "json_extract(w.attributes,'$.title') LIKE ? ESCAPE '\\'",
                "w.business_job LIKE ? ESCAPE '\\'",
            ]
            values.extend([search] * 4)
            # Search the friendly names actually displayed in the table too.
            for job, title in JOB_LABELS.items():
                if filters.search.casefold() in title.casefold():
                    matches.append("w.business_job=?")
                    values.append(job)
            for phase, title in PHASE_LABELS.items():
                if filters.search.casefold() in title.casefold():
                    matches.append("(w.name=? OR w.name LIKE ?)")
                    values.extend([phase, "%." + phase])
            conditions.append("(" + " OR ".join(matches) + ")")
        periods = {"24h": 1, "7d": 7, "30d": 30, "all": None}
        if filters.since not in periods:
            raise ValueError("since must be 24h, 7d, 30d or all")
        if periods[filters.since]:
            conditions.append("w.created_at>=?")
            values.append(int((time.time() - periods[filters.since] * 86400) * 1000))
        return " AND ".join(conditions), values

    def list_runs(self, filters: RunFilters) -> dict:
        """Read one page and exact counts without loading workflow inputs/results."""
        where, values = self._where(filters)
        scope, count_values = self._where(filters, include_status=False)
        with closing(self.panel_connection()) as connection:
            total = connection.execute(
                RUNS + "SELECT COUNT(*) FROM runs w WHERE " + where, values
            ).fetchone()[0]
            counts = dict(
                connection.execute(
                    RUNS + "SELECT w.status, COUNT(*) FROM runs w WHERE "
                    + scope
                    + " GROUP BY w.status",
                    count_values,
                ).fetchall()
            )
            page = min(
                filters.page,
                max(1, (total + filters.page_size - 1) // filters.page_size),
            )
            rows = connection.execute(
                RUNS + "SELECT w.business_job,w.workflow_uuid,w.status,w.name,w.attributes,w.parent_workflow_id,w.queue_name,w.created_at,w.updated_at,w.started_at_epoch_ms,w.completed_at,w.application_version, CASE WHEN w.name='JobWorkflows.dispatch' THEN (SELECT c.name FROM workflow_status c WHERE c.parent_workflow_id=w.workflow_uuid ORDER BY c.created_at LIMIT 1) END AS dispatched, (SELECT COUNT(*) FROM operation_outputs o WHERE o.workflow_uuid=w.workflow_uuid) AS step_count FROM runs w WHERE "
                + where
                + " ORDER BY w.created_at DESC,w.workflow_uuid DESC LIMIT ? OFFSET ?",
                [*values, filters.page_size, (page - 1) * filters.page_size],
            ).fetchall()
        return {
            "items": [summarize(dict(row)) for row in rows],
            "total": total,
            "page": page,
            "page_size": filters.page_size,
            "counts": counts,
            "count_scope": "filters_except_status",
        }

    def get(self, workflow_id: str) -> dict | None:
        """Read one owned metadata row without materializing its serialized payload."""
        with closing(self.connect()) as connection:
            row = connection.execute(
                RUNS + "SELECT business_job,workflow_uuid,status,name,attributes,parent_workflow_id,queue_name,created_at,updated_at,started_at_epoch_ms,completed_at,application_version FROM runs WHERE workflow_uuid=? AND (application_name='assistant' OR application_name IS NULL)",
                (workflow_id,),
            ).fetchone()
        return summarize(dict(row)) if row else None

    def references(self, workflow_id: str) -> dict:
        """Find child and step references, preserving each source and its state."""
        with closing(self.connect()) as connection:
            children = connection.execute(
                "SELECT workflow_uuid,status,name,attributes FROM workflow_status WHERE parent_workflow_id=? AND (application_name='assistant' OR application_name IS NULL) ORDER BY created_at DESC LIMIT 101",
                (workflow_id,),
            ).fetchall()
            parents = connection.execute(
                "SELECT DISTINCT w.workflow_uuid,w.status,w.name,w.attributes FROM workflow_status w JOIN operation_outputs o ON o.workflow_uuid=w.workflow_uuid WHERE o.child_workflow_id=? AND w.workflow_uuid!=? LIMIT 101",
                (workflow_id, workflow_id),
            ).fetchall()
            parent_row = connection.execute(
                "SELECT p.workflow_uuid,p.status,p.name,p.attributes FROM workflow_status w JOIN workflow_status p ON p.workflow_uuid=w.parent_workflow_id WHERE w.workflow_uuid=?",
                (workflow_id,),
            ).fetchone()
            if parent_row and parent_row["workflow_uuid"] not in {
                r["workflow_uuid"] for r in parents
            }:
                parents.append(parent_row)
            step_count = connection.execute(
                "SELECT COUNT(*) FROM operation_outputs WHERE workflow_uuid=?",
                (workflow_id,),
            ).fetchone()[0]

        def brief(rows):
            return [
                {
                    "id": r["workflow_uuid"],
                    "status": r["status"],
                    "title": label(
                        r["name"], json.loads(r["attributes"] or "{}") or {}
                    ),
                }
                for r in rows[:100]
            ]

        business = []
        index = self.directory / "index.sqlite"
        if index.exists():
            with closing(self.connect(index)) as connection:
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='work'"
                ).fetchone()
                if exists:
                    business = [
                        dict(row)
                        for row in connection.execute(
                            "SELECT source_key,page_id,status FROM work WHERE workflow_id=? AND status IN ('Open','Needs Input','Executed') LIMIT 101",
                            (workflow_id,),
                        ).fetchall()
                    ]
        return {
            "children": brief(children),
            "parents": brief(parents),
            "business": business[:100],
            "partial": len(children) > 100 or len(parents) > 100 or len(business) > 100,
            "step_count": step_count,
        }

    def queues(self) -> list[dict]:
        """Report queue totals without interpreting saved job payloads."""
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT queue_name,status,COUNT(*) AS count FROM workflow_status WHERE queue_name IS NOT NULL AND (application_name='assistant' OR application_name IS NULL) GROUP BY queue_name,status ORDER BY queue_name"
            ).fetchall()
        return [dict(row) for row in rows]
