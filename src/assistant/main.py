"""Wire proposal, execution, and accepted-result curation services."""

import asyncio
import json
import os

from assistant.config import load_settings
from assistant.protocol.proposer import ProposerProtocol
from assistant.protocol.router import RouterProtocol
from assistant.protocol.investigator import InvestigatorProtocol
from assistant.protocol.task import TaskRunnerProtocol, TaskWorkerProtocol
from assistant.protocol.workbench import WorkbenchProtocol
from assistant.protocol.curator import ArchiveStoreProtocol, CuratorProtocol
from providers import get_provider
from logger import get_logger

os.environ["PYDANTIC_AI_NO_BANNER"] = "1"


def main() -> None:
    """Run one manually or externally scheduled assistant cycle.

    Proposal maintenance runs first. New proposals always wait for a later
    human decision; main only assembles interfaces and invokes the services.
    """
    logger = get_logger("assistant.main")
    config = load_settings()

    # Providers own connections and workflow details; main only binds interfaces.
    storage_name = config.providers.workbench
    storage_provider = get_provider(storage_name)
    workbench: WorkbenchProtocol = storage_provider.Workbench(
        config.provider_options[storage_name],
    )

    proposer_name = config.providers.proposer
    proposer_provider = get_provider(proposer_name)
    proposer: ProposerProtocol = proposer_provider.Proposer(
        config.provider_options[proposer_name], workbench=workbench,
    )

    router_name = config.providers.router
    router_provider = get_provider(router_name)
    router: RouterProtocol = router_provider.DecisionRouter(config.provider_options[router_name])

    worker_name = config.providers.worker
    worker_provider = get_provider(worker_name)
    worker: TaskWorkerProtocol = worker_provider.TaskWorker(config.provider_options[worker_name])

    investigator_name = config.providers.investigator
    investigator_provider = get_provider(investigator_name)
    investigator: InvestigatorProtocol = investigator_provider.Investigator(
        config.provider_options[investigator_name],
    )

    execution_provider = get_provider(config.providers.execution)
    runner: TaskRunnerProtocol = execution_provider.TaskRunner(
        workbench=workbench, router=router, worker=worker, investigator=investigator,
    )

    archive_name = config.providers.archive
    archive_provider = get_provider(archive_name)
    archive: ArchiveStoreProtocol = archive_provider.ArchiveStore(
        config.provider_options[archive_name],
    )

    curator_name = config.providers.curator
    curator_provider = get_provider(curator_name)
    curator: CuratorProtocol = curator_provider.Curator(
        config.provider_options[curator_name], workbench=workbench, archive=archive,
    )

    logger.info("Starting one assistant cycle.")
    output = asyncio.run(run_cycle(proposer, runner, curator))
    logger.info(json.dumps(output, ensure_ascii=False, indent=2))


async def run_cycle(
    proposer: ProposerProtocol, runner: TaskRunnerProtocol, curator: CuratorProtocol,
) -> dict:
    """Invoke independent services in an order that preserves human approval.

    Args:
        proposer: Service maintaining reviews and accepting new source material.
        runner: Service executing at most one previously approved proposal.
        curator: Service finalizing only human-accepted results.

    Returns:
        Proposal, execution, and finalization summaries for this invocation.
    """
    proposals = await proposer.run_cycle()
    execution = await runner.run_cycle()
    curation = await curator.run_cycle()
    output = {
        "proposals": proposals.model_dump(),
        "execution": execution.model_dump(),
        "curation": curation.model_dump(),
    }
    return output


if __name__ == "__main__":
    main()
