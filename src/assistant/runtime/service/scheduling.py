"""Manage desired recurring jobs from local YAML through DBOS runtime APIs.

Input: browser edits with a configuration revision, or startup configuration.
Output: atomic YAML schedule updates and synchronized DBOS schedules. Provider
settings are never sent to the browser. Accepted jobs remain independent of edits.
"""

import asyncio
from datetime import datetime
import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from croniter import croniter
from dbos import DBOS
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException
from starlette.routing import Route
from yaml import compose, safe_dump, safe_load
from yaml.nodes import MappingNode
from zoneinfo import ZoneInfo

from assistant.config import ScheduleSettings, schedule_settings
from assistant.runtime import schedules
from assistant.runtime.service.metadata import JOB_LABELS
from assistant.runtime.service.submissions import TRIGGER_QUEUE
from logger import get_logger

logger = get_logger("runtime.service.scheduling")


class ScheduleEdit(ScheduleSettings):
    """Require a revision for replacing one job's desired schedule."""

    revision: str


class ScheduleRevision(BaseModel):
    """Protect deletion from overwriting another operator's edit."""

    model_config = ConfigDict(extra="forbid")
    revision: str


def next_times(spec: ScheduleSettings) -> list[str]:
    """Preview the next five actual trigger instants in the selected time zone."""
    iterator = croniter(
        spec.cron,
        datetime.now(ZoneInfo(spec.timezone)),
        second_at_beginning=True,
        max_years_between_matches=8,
    )
    return [iterator.get_next(datetime).isoformat() for _ in range(5)]


def replace_schedules(content, desired):
    """Replace the schedule block while retaining all surrounding YAML text."""
    root = compose(content)
    for key, runtime in root.value:
        if key.value == "runtime" and isinstance(runtime, MappingNode):
            for field, value in runtime.value:
                if field.value == "schedules":
                    lines = content.splitlines(keepends=True)
                    end = value.end_mark.line + (1 if value.flow_style else 0)
                    block = safe_dump(
                        {"schedules": desired}, allow_unicode=True, sort_keys=False
                    )
                    replacement = [
                        " " * field.start_mark.column + line + "\n"
                        for line in block.splitlines()
                    ]
                    lines[field.start_mark.line : end] = replacement
                    return "".join(lines)
    document = safe_load(content)
    document.setdefault("runtime", {})["schedules"] = desired
    return safe_dump(document, allow_unicode=True, sort_keys=False)


class ScheduleManager:
    """Keep local desired configuration and the live scheduler visibly aligned."""

    def __init__(self, settings):
        """Bind settings without opening DBOS or modifying configuration."""
        self.settings = settings
        self.path = getattr(settings, "_source", None)
        self.lock = asyncio.Lock()

    def revision(self):
        """Hash the source snapshot so stale forms cannot overwrite newer edits."""
        return hashlib.sha256(self.path.read_bytes()).hexdigest() if self.path else None

    def snapshot(self):
        """Read desired values and their revision from one source snapshot."""
        if not self.path:
            return dict(self.settings.runtime.schedules), None
        raw = self.path.read_bytes()
        desired = safe_load(raw).get("runtime", {}).get("schedules", {})
        if not isinstance(desired, dict):
            raise ValueError("runtime.schedules must be a mapping")
        return {
            job: ScheduleSettings.model_validate(value)
            if isinstance(value, dict)
            else schedule_settings(value)
            for job, value in desired.items()
        }, hashlib.sha256(raw).hexdigest()

    async def sync(self):
        """Apply desired schedules while preserving unchanged firing history."""
        desired, _ = await asyncio.to_thread(self.snapshot)
        unknown = set(desired) - set(JOB_LABELS)
        if unknown:
            raise ValueError("Unknown scheduled jobs: " + ", ".join(sorted(unknown)))
        self.settings.runtime.schedules = desired
        logger.info("Synchronizing recurring jobs: configured=%d.", len(desired))
        current = {
            item["schedule_name"]: item for item in await DBOS.list_schedules_async()
        }
        for job, raw in desired.items():
            spec = schedule_settings(raw)
            name = "assistant-" + job
            old = current.get(name)
            changed = (
                not old
                or old["schedule"] != spec.cron
                or old.get("cron_timezone") != spec.timezone
                or old.get("context") != {"job": job}
                or old.get("queue_name") != TRIGGER_QUEUE
            )
            if changed:
                await DBOS.apply_schedules_async(
                    [
                        {
                            "schedule_name": name,
                            "workflow_fn": schedules.scheduled_job,
                            "schedule": spec.cron,
                            "cron_timezone": spec.timezone,
                            "context": {"job": job},
                            "automatic_backfill": False,
                            "queue_name": TRIGGER_QUEUE,
                        }
                    ]
                )
            actual_status = "ACTIVE" if changed else old["status"]
            if not spec.enabled and actual_status != "PAUSED":
                await asyncio.to_thread(DBOS.pause_schedule, name)
            elif spec.enabled and actual_status != "ACTIVE":
                await asyncio.to_thread(DBOS.resume_schedule, name)
        for name in current:
            if (
                name.startswith("assistant-")
                and name.removeprefix("assistant-") not in desired
            ):
                await DBOS.delete_schedule_async(name)
        logger.info("Recurring jobs synchronized: configured=%d.", len(desired))

    async def listing(self):
        """Combine desired schedules, live status and future trigger previews."""
        logger.debug("Reading daily-job configuration and live schedule states.")
        current = {
            item["schedule_name"]: item for item in await DBOS.list_schedules_async()
        }
        desired, revision = await asyncio.to_thread(self.snapshot)
        items = []
        for job, raw in desired.items():
            spec = schedule_settings(raw)
            actual = current.get("assistant-" + job)
            expected = "ACTIVE" if spec.enabled else "PAUSED"
            synced = bool(
                actual
                and actual["schedule"] == spec.cron
                and actual.get("cron_timezone") == spec.timezone
                and actual["status"] == expected
            )
            items.append(
                {
                    "job": job,
                    "title": JOB_LABELS.get(job, job),
                    **spec.model_dump(),
                    "status": actual["status"] if actual else "MISSING",
                    "synced": synced,
                    "next_runs": next_times(spec) if spec.enabled else [],
                    "last_fired_at": actual.get("last_fired_at") if actual else None,
                }
            )
        logger.debug(
            "Daily-job states read: configured=%d synchronized=%d.",
            len(items),
            sum(item["synced"] for item in items),
        )
        return {
            "items": items,
            "revision": revision,
            "pending_removals": [
                name
                for name in current
                if name.startswith("assistant-")
                and name.removeprefix("assistant-") not in desired
            ],
            "editable": self.path is not None,
        }

    def persist(self, job, spec, revision):
        """Atomically write only desired schedule values, preserving other settings."""
        if self.path is None:
            raise HTTPException(
                405, "This runtime has no writable configuration source"
            )
        if self.revision() != revision:
            raise HTTPException(409, "配置已被修改，请刷新后重新编辑")
        document = safe_load(self.path.read_text(encoding="utf-8"))
        desired = document.setdefault("runtime", {}).setdefault("schedules", {})
        if spec is None:
            desired.pop(job, None)
        else:
            desired[job] = spec.model_dump()
        content = replace_schedules(self.path.read_text(encoding="utf-8"), desired)
        safe_load(content)  # Validate the complete YAML before replacing its source.
        # A separate file plus replace prevents a stopped service leaving half YAML.
        temporary = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                os.chmod(temporary, self.path.stat().st_mode & 0o777)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if self.revision() != revision:
                raise HTTPException(409, "配置已被修改，请刷新后重新编辑")
            os.replace(temporary, self.path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        # Publish the complete snapshot to the trigger gate with one assignment.
        self.settings.runtime.schedules = {
            key: ScheduleSettings.model_validate(value)
            if isinstance(value, dict)
            else value
            for key, value in desired.items()
        }

    async def change(self, job, spec, revision):
        """Save desired state, then synchronize; report a retryable split explicitly."""
        async with self.lock:
            logger.info(
                "Saving recurring job: job=%s operation=%s.",
                job,
                "delete" if spec is None else "update",
            )
            await asyncio.to_thread(self.persist, job, spec, revision)
            try:
                await self.sync()
            except Exception as error:
                logger.exception(
                    "Schedule saved but live synchronization failed: job=%s.", job
                )
                raise HTTPException(
                    503, "配置已保存，但 DBOS 同步失败。请点击“同步配置”重试。"
                ) from error
            logger.info("Recurring job saved and applied: job=%s.", job)
            return await self.listing()


def routes(manager, respond):
    """Expose schedule CRUD and preview without arbitrary workflow execution."""

    async def listing(request):
        return respond(await manager.listing())

    async def preview(request):
        spec = ScheduleSettings.model_validate(await request.json())
        return respond({"next_runs": next_times(spec)})

    async def update(request):
        job = request.path_params["job"]
        require_job(job)
        edit = ScheduleEdit.model_validate(await request.json())
        spec = ScheduleSettings.model_validate(edit.model_dump(exclude={"revision"}))
        return respond(await manager.change(job, spec, edit.revision))

    async def delete(request):
        job = request.path_params["job"]
        require_job(job)
        edit = ScheduleRevision.model_validate(await request.json())
        return respond(await manager.change(job, None, edit.revision))

    async def sync(request):
        async with manager.lock:
            await manager.sync()
        return respond(await manager.listing())

    return [
        Route("/panel/schedules", listing),
        Route("/panel/schedules/preview", preview, methods=["POST"]),
        Route("/panel/schedules/sync", sync, methods=["POST"]),
        Route("/panel/schedules/{job}", update, methods=["PUT"]),
        Route("/panel/schedules/{job}", delete, methods=["DELETE"]),
    ]


def require_job(job):
    """Restrict schedule control to the same job catalog as manual submissions."""
    if job not in JOB_LABELS:
        raise HTTPException(404, "Unknown job")
