"""Expose shared logging, operation context, and CLI verbosity selection.

Input origin:
    Application modules request loggers and emit business messages with optional
    structured details. main.py selects verbose mode after parsing CLI options.

Output destination:
    Shared console/file handlers render the current operation and readable
    progress. configure_logging adds details and traceback output when the user
    requests -v; severity thresholds and JSON business output are unaffected.

Boundaries:
    Importing the package does not create files or launch workflows. Logging
    configuration and call context do not choose actions or change workflow state.
"""

import logging

from .base_config import BaseConfig
from .base_logger import BaseLogger
from .multi_line_formatter import MultiLineFormatter
from .call_context import CallContextFilter, call_scope, trace_call


def get_logger(name: str = "assistant") -> logging.Logger:
    """Get a standard logger sharing the assistant's configured handlers.

    Args:
        name: Root name, assistant-prefixed name, or component name.

    Returns:
        Standard logger using shared assistant console/file output.
    """
    BaseLogger()

    if name == "assistant" or name.startswith("assistant."):
        logger_name = name
    else:
        logger_name = f"assistant.{name}"

    logger = logging.getLogger(logger_name)
    if not any(isinstance(item, CallContextFilter) for item in logger.filters):
        logger.addFilter(CallContextFilter())
    return logger


def configure_logging(*, verbose: bool = False) -> None:
    """Choose diagnostic detail without changing severity filtering.

    Args:
        verbose: Include diagnostic fields and full tracebacks on emitted records.
    """
    logger = get_logger()
    for handler in logger.handlers:
        formatter = handler.formatter
        if isinstance(formatter, MultiLineFormatter):
            formatter.verbose = verbose


__all__ = [
    "BaseConfig", "BaseLogger", "MultiLineFormatter", "get_logger",
    "configure_logging", "call_scope", "trace_call",
]
