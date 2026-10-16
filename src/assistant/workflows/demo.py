"""Demonstrate daily intake and human-reviewed work using print-only steps."""

from datetime import datetime

from dbos import DBOS


DEMO_DAY_SECONDS = 10


@DBOS.step()
def read_inputs(batch: str) -> list[dict[str, str]]:
    """Simulate reading unarchived Inbox items and elevated TODO items.

    Args:
        batch: Scheduled time identifying this intake batch.

    Returns:
        Two simulated inputs with distinct source identifiers.
    """
    print(f"[{batch}] Intake: Inbox != Archived; TODO = elevated", flush=True)
    sources = [
        {"id": f"inbox-{batch}", "kind": "Inbox", "text": "Calculate 1 + 1."},
        {"id": f"todo-{batch}", "kind": "TODO", "text": "Explain a reusable research method."},
    ]
    return sources


@DBOS.step()
def record_stage(source_id: str, stage: str, detail: str) -> None:
    """Print a simulated operation instead of calling a provider.

    Args:
        source_id: Identifier connecting the proposal to its input.
        stage: Operation or Workbench status being demonstrated.
        detail: Human-readable description of the simulated change.
    """
    print(f"[{source_id}] {stage}: {detail}", flush=True)


@DBOS.step()
def simulate_review(source_id: str, phase: str, scenario: str, attempt: int) -> str:
    """Supply scripted human feedback; this is not a real approval integration.

    Args:
        source_id: Proposal being reviewed.
        phase: Either proposal approval or result acceptance.
        scenario: approved, revision, rejected, or unqualified demo path.
        attempt: Review attempt, starting at one.

    Returns:
        The scripted review decision.
    """
    decision = "Approved" if phase == "proposal" else "Qualified"
    if phase == "proposal" and scenario == "rejected":
        decision = "Rejected"
    elif phase == "proposal" and scenario == "revision" and attempt == 1:
        decision = "Revision Requested"
    elif phase == "result" and scenario == "unqualified" and attempt == 1:
        decision = "Unqualified"

    print(f"[{source_id}] SIMULATED human {phase} review: {decision}", flush=True)
    return decision


@DBOS.workflow()
def proposal_lifecycle(source: dict[str, str], scenario: str) -> None:
    """Demonstrate proposal, approval, execution, acceptance, and curation.

    Args:
        source: Simulated input including its identifier, kind, and content.
        scenario: Scripted review path to exercise.
    """
    source_id = source["id"]
    record_stage(source_id, "Open", f"Publish proposal with source, purpose, and reason: {source['text']}")

    # Intake acknowledgement follows proposal publication, not result acceptance.
    source_status = "Archived" if source["kind"] == "Inbox" else "handled"
    record_stage(source_id, "Source acknowledged", f"{source['kind']} -> {source_status}")

    attempt = 1
    while True:
        record_stage(source_id, "Waiting", "Proposal awaits simulated human approval for one demo day.")
        DBOS.sleep(DEMO_DAY_SECONDS)
        decision = simulate_review(source_id, "proposal", scenario, attempt)

        if decision == "Rejected":
            record_stage(source_id, "Deprecated", "Rejected proposal will not execute.")
            return
        if decision == "Approved":
            break

        record_stage(source_id, "Open", "Revise proposal using feedback and resubmit for approval.")
        attempt += 1

    attempt = 1
    while True:
        # In the real workflow this boundary dispatches to the execution service.
        record_stage(source_id, "Execute", f"Route approved work to an executor; attempt {attempt}.")
        result = "1 + 1 = 2" if source["kind"] == "Inbox" else "A reusable method with supporting evidence."
        record_stage(source_id, "Executed", f"Save result to the same Workbench item: {result}")

        record_stage(source_id, "Waiting", "Result awaits simulated human acceptance for one demo day.")
        DBOS.sleep(DEMO_DAY_SECONDS)
        decision = simulate_review(source_id, "result", scenario, attempt)
        if decision == "Qualified":
            break

        record_stage(source_id, "Rework", "Redo execution using human feedback; do not curate yet.")
        attempt += 1

    # Only qualified results reach curation. Intermediate work stays in Workbench.
    if source["kind"] == "Inbox":
        record_stage(source_id, "Finished", "Curator finds no reusable knowledge; no archive publication.")
    else:
        record_stage(source_id, "Curate", "Extract useful knowledge and publish it to Knowledge (simulated).")
        record_stage(source_id, "Archived", "Archive publication verified (simulated); close Workbench item.")


@DBOS.workflow()
def daily_intake(scheduled_time: datetime, context: dict[str, str]) -> None:
    """Start independent proposal lifecycles for one simulated day's inputs.

    Args:
        scheduled_time: DBOS firing time identifying this day's intake batch.
        context: Demo parameters; scenario selects the scripted review path.
    """
    batch = scheduled_time.isoformat()
    sources = read_inputs(batch)

    # Do not wait for human review before processing the next day's inputs.
    for source in sources:
        DBOS.start_workflow(proposal_lifecycle, source, context["scenario"])
