"""Read optional Codex execution telemetry independently of business results."""

import json

from assistant.schemas.process import ExecutionProcess


def read_process(output: str) -> ExecutionProcess:
    """Collect JSON events and token usage from Codex stdout.

    Args:
        output: Codex stdout, possibly containing non-JSON diagnostic lines.

    Returns:
        Ordered event objects and the last available completed-turn usage.
        Unknown event types and additional fields are preserved.
    """
    events = []
    usage = {}

    for line in output.splitlines():
        if not line.strip():
            continue

        # Telemetry noise must not invalidate an otherwise valid result file.
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(event, dict):
            continue

        events.append(event)

        if event.get("type") == "turn.completed":
            reported_usage = event.get("usage")
            if isinstance(reported_usage, dict) and reported_usage:
                usage = reported_usage

    process = ExecutionProcess(events=events, usage=usage)
    return process
