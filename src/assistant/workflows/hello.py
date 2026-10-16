"""Provide a minimal checkpointed workflow for exercising the DBOS runtime."""

from datetime import datetime

from dbos import DBOS


@DBOS.step()
def print_greeting(n: int) -> str:
    """Print a greeting as a checkpointed side effect.

    Args:
        n: Value included in the greeting, not a persistent execution counter.

    Returns:
        The greeting printed by this step.
    """
    greeting = f"hello world {n}"
    print(greeting, flush=True)
    return greeting


@DBOS.workflow()
def hello_world(n: int) -> str:
    """Execute the greeting workflow manually or through a schedule.

    Args:
        n: Value to include in the greeting.

    Returns:
        The completed greeting.
    """
    greeting = print_greeting(n)
    return greeting


@DBOS.workflow()
def scheduled_hello(scheduled_time: datetime, context: dict[str, int]) -> str:
    """Adapt a DBOS schedule invocation to the greeting workflow.

    Args:
        scheduled_time: Intended firing time supplied by DBOS.
        context: Schedule parameters containing the greeting value under n.

    Returns:
        The greeting produced by the child workflow.
    """
    DBOS.logger.info("Running hello-world scheduled for %s.", scheduled_time)
    greeting = hello_world(context["n"])
    return greeting
