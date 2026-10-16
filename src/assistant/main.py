"""Run explicit assistant jobs or opt into durable DBOS schedules."""

import argparse
import asyncio
import fcntl
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dbos import DBOS, DBOSConfig
from pydantic import BaseModel

from assistant.config import AssistantConfig, load_settings
from assistant.services import Services
from assistant.schemas.recommendation import CATEGORIES, RecommendationRun
from assistant.workflows.index import WorkIndex
from assistant.workflows.jobs import JobWorkflows
from assistant.workflows.proposals import ProposalWorkflows
from assistant.workflows.research import ResearchWorkflows
from assistant.workflows.recovery import recover


JOBS = ("intake", "reviews", "papers", "articles", "recommendations")
SHANGHAI = ZoneInfo("Asia/Shanghai")
# DBOS schedules require a module-level function, not a configured instance method.
_jobs: JobWorkflows | None = None
_serving = False


@DBOS.workflow()
async def scheduled_job(scheduled_time: datetime, context: dict[str, str]):
    """Dispatch an explicitly enabled schedule through the configured application.

    Args:
        scheduled_time: DBOS-supplied scheduled instant.
        context: Persisted job name, without credentials or provider objects.

    Returns:
        Job output, or None when the application was launched in manual mode.
    """
    if not _serving or context["job"] not in _jobs.settings.schedules:
        return None
    day = scheduled_time.astimezone(SHANGHAI).date().isoformat()
    output = await _jobs.dispatch(context["job"], day)
    return output


def arguments() -> argparse.Namespace:
    """Parse finite jobs separately from the long-running scheduler.

    Returns:
        Selected command and optional isolated configuration path.
    """
    parser = argparse.ArgumentParser(description="Personal research assistant with DBOS checkpoints")

    parser.add_argument("--config", type=Path, help="Alternate YAML configuration")

    commands = parser.add_subparsers(dest="command", required=True)

    # Finite jobs that can be run explicitly outside of the scheduler.
    run = commands.add_parser("run", help="Run one finite job")
    run.add_argument("job", choices=JOBS)
    run.add_argument("--page", help="Explicit raw page for papers/articles reprocessing")

    # Long-running scheduler command.
    commands.add_parser("serve", help="Run only the schedules enabled in YAML")

    # Status command to list persisted schedules and recent workflows.
    commands.add_parser("status", help="List persisted schedules and recent workflows")

    # Resume command to continue unfinished workflows.
    resume = commands.add_parser("resume", help="Resume unfinished steps of a failed workflow")
    resume.add_argument("workflow_id")

    # Setup command to initialize required Notion schema additions.
    commands.add_parser("setup", help="Explicitly initialize required Notion schema additions")
    
    options = parser.parse_args()
    return options


async def run_command(options: argparse.Namespace):
    """Execute a finite job or resume an existing durable operation.

    Args:
        options: Parsed command.

    Returns:
        Actual workflow output.
    """
    if options.command == "resume":
        handle = await recover(options.workflow_id)
    else:
        day = datetime.now(SHANGHAI).date().isoformat()
        handle = await DBOS.start_workflow_async(_jobs.dispatch, options.job, day, options.page)
    output = await handle.get_result()
    return output


def display(output) -> None:
    """Print business outputs without exposing configuration or model credentials.

    Args:
        output: Workflow report or collection of verified destination links.
    """
    document = output.model_dump(mode="json") if isinstance(output, BaseModel) else output
    if isinstance(output, RecommendationRun):
        counts = {category: 0 for category in CATEGORIES}
        real = [entry for entry in output.selected if not entry.candidate.demo]
        for _, entry in zip(output.published, real):
            counts[entry.assessment.category] += 1
        document.update(
            publication_count=len(output.published), publication_counts=counts,
            short_term_interest_changes=[],
        )
    print(json.dumps(document, ensure_ascii=False, indent=2, default=str))


def initialize_schema(services: Services) -> None:
    """Initialize only the Notion additions used by these workflows.

    Args:
        services: Configured storage providers.
    """
    services.workbench.initialize_schema()
    services.archive.initialize_schema()
    services.feed.initialize_schema()


async def application(options: argparse.Namespace, settings: AssistantConfig, services: Services) -> None:
    """Keep scheduled and recovered workflows on the active application loop.

    Args:
        options: Requested CLI operation.
        settings: Application and runtime configuration.
        services: Lazily bound providers.
    """
    DBOS.launch()
    try:
        if options.command == "serve":
            await DBOS.register_queue_async("assistant-jobs", worker_concurrency=1)
            enabled = settings.runtime.schedules
            for schedule in await DBOS.list_schedules_async():
                name = schedule["schedule_name"]
                if name.startswith("assistant-") and name.removeprefix("assistant-") not in enabled:
                    await asyncio.to_thread(DBOS.pause_schedule, name)
            definitions = [
                {
                    "schedule_name": "assistant-" + job, "workflow_fn": scheduled_job,
                    "schedule": cron, "cron_timezone": "Asia/Shanghai",
                    "context": {"job": job}, "automatic_backfill": False,
                    "queue_name": "assistant-jobs",
                }
                for job, cron in enabled.items()
            ]
            await DBOS.apply_schedules_async(definitions)
            print(f"Enabled schedules: {list(enabled)}. Ctrl+C to stop.")
            await asyncio.Event().wait()
        elif options.command == "status":
            schedules = await DBOS.list_schedules_async()
            workflows = await DBOS.list_workflows_async(
                limit=20, sort_desc=True, load_input=False, load_output=False,
            )
            display({"schedules": schedules, "workflows": [
                {"id": item.workflow_id, "status": item.status, "name": item.name}
                for item in workflows
            ]})
        elif options.command == "setup":
            await asyncio.to_thread(initialize_schema, services)
            print("Required Notion schema additions initialized; existing properties retained.")
        else:
            display(await run_command(options))
    finally:
        # Keep the event loop available while queue workers finish their callbacks.
        await asyncio.to_thread(DBOS.destroy, workflow_completion_timeout_sec=10)


def main() -> None:
    """Compose capabilities and launch manual jobs or explicitly enabled schedules."""
    global _jobs, _serving
    options = arguments()
    settings = load_settings(options.config)
    directory = Path(settings.runtime.directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)

    # One local process owns this runtime; scheduling and manual runs cannot overlap.
    with (directory / "runtime.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        services = Services(settings)
        index = WorkIndex(directory / "index.sqlite")
        proposals = ProposalWorkflows(services, index, directory)
        research = ResearchWorkflows(services, index, directory, settings.runtime.recommendation_maxima)
        _jobs = JobWorkflows(services, proposals, research, index, settings.runtime)
        _serving = options.command == "serve"
        config: DBOSConfig = {
            "name": "assistant", "system_database_url": f"sqlite:///{directory / 'dbos.sqlite'}",
        }
        DBOS(config=config)
        try:
            asyncio.run(application(options, settings, services))
        except KeyboardInterrupt:
            print("Stopping the assistant runtime.")


if __name__ == "__main__":
    main()
