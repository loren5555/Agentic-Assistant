"""Identify the active operation without printing its entire call ancestry.

Input origin:
    Commands, DBOS workflow/step bodies, and component methods enter named scopes
    through trace_call or call_scope. Context variables isolate concurrent tasks.

Output destination:
    Records retain call context, but console/file output shows only the current
    operation by default. Explicit business messages describe actual progress.

Boundaries:
    Scopes describe execution, not argument values or durable state. No payload,
    credentials, or model prompts are recorded here. Cached DBOS steps do not
    enter their decorated bodies and therefore do not claim fresh execution.
    Entering or leaving a scope does not emit a generic lifecycle message.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, Callable, Iterator
import logging

_path: ContextVar[tuple[str, ...]] = ContextVar("assistant_call_path", default=())


def current_call_path() -> str:
    """Return the current logical call chain without exposing input values.

    Returns:
        Named scopes joined in caller-to-callee order, or '-' outside a scope.
    """
    path = " > ".join(_path.get()) or "-"
    return path


def current_operation() -> str:
    """Return only the innermost active operation.

    Returns:
        Current command/workflow/step/component/tool label, or '-' when idle.
    """
    path = _path.get()
    operation = path[-1] if path else "-"
    return operation


class CallContextFilter(logging.Filter):
    """Attach context before handlers format or retain a logging record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach the current call path while preserving explicit record context.

        Args:
            record: Record emitted by a configured assistant logger.

        Returns:
            True, without changing the record's severity or message.
        """
        if not hasattr(record, "call_path"):
            record.call_path = current_call_path()
        if not hasattr(record, "operation"):
            operation = current_operation()
            record.operation = operation if operation != "-" else record.name.removeprefix("assistant.")
        return True


@contextmanager
def call_scope(kind: str, name: str) -> Iterator[None]:
    """Set the current operation without adding duplicate lifecycle logs.

    Args:
        kind: Command, workflow, step, component, or tool boundary.
        name: Logical operation name, not a user-provided payload.

    Yields:
        Control to the operation with its call context active.
    """
    token = _path.set((*_path.get(), f"{kind}:{name}"))
    try:
        yield
    finally:
        _path.reset(token)


def trace_call(
    kind: str, name: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a real call boundary while retaining its public signature.

    Args:
        kind: Layer to display in the call path.
        name: Named workflow, step, component operation, or command.

    Returns:
        Decorator supporting synchronous functions and coroutine functions.
    """
    def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap an operation without evaluating or logging its arguments.

        Args:
            function: Original operation whose metadata must be preserved.

        Returns:
            Signature-preserving wrapper with a task-local scope.
        """
        if iscoroutinefunction(function):
            @wraps(function)
            async def run_async(*args: Any, **kwargs: Any) -> Any:
                """Run the coroutine inside its call scope.

                Args:
                    *args: Original positional arguments, forwarded unchanged.
                    **kwargs: Original keyword arguments, forwarded unchanged.

                Returns:
                    The original coroutine's result.
                """
                with call_scope(kind, name):
                    result = await function(*args, **kwargs)
                return result

            return run_async

        @wraps(function)
        def run_sync(*args: Any, **kwargs: Any) -> Any:
            """Run the function inside its call scope.

            Args:
                *args: Original positional arguments, forwarded unchanged.
                **kwargs: Original keyword arguments, forwarded unchanged.

            Returns:
                The original function's result.
            """
            with call_scope(kind, name):
                result = function(*args, **kwargs)
            return result

        return run_sync

    return decorate
