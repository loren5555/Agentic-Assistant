"""Readable assistant logs with no setup or file creation during import."""

import logging

from .base_config import BaseConfig
from .base_logger import BaseLogger
from .multi_line_formatter import MultiLineFormatter


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
    return logger


__all__ = ["BaseConfig", "BaseLogger", "MultiLineFormatter", "get_logger"]
