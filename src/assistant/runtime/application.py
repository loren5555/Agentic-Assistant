"""Compose the application and register durable functions before recovery starts."""

from __future__ import annotations

from pathlib import Path
import argparse
import asyncio

from dbos import DBOS, DBOSConfig, DBOSConfiguredInstance

from assistant.commands import run as run_command
from assistant.config import AssistantConfig, RuntimeSettings
from assistant.runtime.index import WorkIndex
from assistant.runtime.records import install_checkpoint_aliases
from assistant.runtime.services import Services
from assistant.workflows.steps import submit_proposal as proposal_steps, organize_capture as capture_steps
from assistant.workflows.tasks import organize_papers as papers_task, organize_articles as articles_task
from assistant.workflows.tasks import propose_tasks as proposal_task, process_workbench as workbench_task
from assistant.workflows.tasks.recommend_papers import RecommendationWorkflows
from logger import get_logger


@DBOS.dbos_class("JobWorkflows")
class TaskWorkflows(DBOSConfiguredInstance):
    """Bind task methods under the stable DBOS class/instance identity.

    Business implementations live exclusively in workflows/tasks and workflows/steps.
    """

    def __init__(self, services: Services, proposals: WorkbenchWorkflows, research: RecommendationWorkflows,
                 index: WorkIndex, settings: RuntimeSettings) -> None:
        """Register dependencies before DBOS launches recovery.

        Args:
            services: Provider-facing capabilities.
            proposals: Item-level proposal workflows.
            research: Recommendation workflows.
            index: Local source and cursor index.
            settings: Runtime settings.
        """
        super().__init__("jobs")
        self.services = services
        self.proposals = proposals
        self.research = research
        self.index = index
        self.settings = settings

    read_inputs = proposal_task.read_inputs
    lookup = proposal_task.lookup
    load_previous = proposal_task.load_previous
    list_active = workbench_task.list_active
    read_capture_batch = capture_steps.read_capture_batch
    brief = capture_steps.brief
    publish_capture = capture_steps.publish_capture
    save_capture_checkpoint = capture_steps.save_capture_checkpoint
    acknowledge_capture = capture_steps.acknowledge_capture
    capture_item = capture_steps.capture_item
    save_cursor = capture_steps.save_cursor
    organize_captures = capture_steps.organize_captures
    read_capture = capture_steps.read_capture
    propose_tasks = proposal_task.propose_tasks
    process_workbench = workbench_task.process_workbench
    organize_papers = papers_task.organize_papers
    organize_articles = articles_task.organize_articles
    dispatch = run_command.dispatch


@DBOS.dbos_class("ProposalWorkflows")
class WorkbenchWorkflows(DBOSConfiguredInstance):
    """Bind shared submission and review steps for durable Workbench state."""

    def __init__(self, services: Services, index: WorkIndex, directory: Path) -> None:
        """Bind dependencies and register the stable DBOS instance name.

        Args:
            services: Lazy provider implementations.
            index: Application-owned lookup store.
            directory: Location for detailed runtime reports.
        """
        super().__init__("proposals")
        self.services = services
        self.index = index
        self.directory = directory

    save_checkpoint = proposal_steps.save_checkpoint
    read_source = proposal_steps.read_source
    read_current_source = proposal_steps.read_current_source
    draft = proposal_steps.draft
    publish_proposal = proposal_steps.publish_proposal
    acknowledge = proposal_steps.acknowledge
    submit_proposal = proposal_steps.submit_proposal
    read_review = workbench_task.read_review
    route = workbench_task.route
    decide = workbench_task.decide
    execute = workbench_task.execute
    save_result = workbench_task.save_result
    save_error = workbench_task.save_error
    check_authorization = workbench_task.check_authorization
    extract = workbench_task.extract
    publish_artifact = workbench_task.publish_artifact
    close_item = workbench_task.close_item
    review_item = workbench_task.review_item
    request_input = workbench_task.request_input


class Application:
    """Own configuration, provider bindings, and the local DBOS lifetime.

    Attributes:
        settings: Parsed application configuration.
        services: Lazy implementations of component protocols.
        tasks: Registered complete tasks available to run and serve.
    """

    def __init__(self, settings: AssistantConfig) -> None:
        """Compose all durable instances before DBOS can recover saved work.

        Args:
            settings: Provider choices, storage paths, and enabled schedules.
        """
        self.settings = settings
        get_logger("runtime.application").debug(
            "Providers selected: proposer=%s router=%s worker=%s investigator=%s captures=%s discovery=%s.",
            settings.providers.proposer, settings.providers.router, settings.providers.worker,
            settings.providers.investigator, settings.providers.captures, settings.providers.discovery,
        )
        directory = Path(settings.runtime.directory).resolve()
        self.services = Services(settings)
        index = WorkIndex(directory / "index.sqlite")
        proposals = WorkbenchWorkflows(self.services, index, directory)
        research = RecommendationWorkflows(self.services, index, directory, settings.runtime.recommendation_maxima)
        self.tasks = TaskWorkflows(self.services, proposals, research, index, settings.runtime)
        install_checkpoint_aliases()
        config: DBOSConfig = {
            "name": "assistant", "system_database_url": f"sqlite:///{directory / 'dbos.sqlite'}",
            "log_level": "WARNING",
            "console_log_level": "WARNING",
        }
        DBOS(config=config)

    async def execute(self, options: argparse.Namespace) -> None:
        """Start DBOS, dispatch one command, and allow orderly shutdown.

        Args:
            options: Selected command and its arguments.
        """
        from assistant.commands import setup, serve, status, resume
        from assistant.runtime import schedules

        logger = get_logger("runtime.application")
        schedules.bind(self, serving=options.command == "serve")
        logger.info("Starting DBOS: command=%s; unfinished workflows may recover.", options.command)
        DBOS.launch()
        try:
            if options.command == "setup":
                await setup.run(self, options)
            elif options.command == "run":
                await run_command.run(self, options)
            elif options.command == "serve":
                await serve.run(self, options)
            elif options.command == "status":
                await status.run(self, options)
            elif options.command == "resume":
                await resume.run(self, options)
            else:
                raise ValueError(f"Unsupported command: {options.command}")
        finally:
            logger.info("Stopping DBOS: allowing up to 10 seconds for active workflows.")
            await asyncio.to_thread(DBOS.destroy, workflow_completion_timeout_sec=10)
            logger.info("DBOS stopped.")
