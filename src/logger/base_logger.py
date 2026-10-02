"""Explicit setup for shared console and optional file logging."""

import logging
import sys
from typing import Any, Self

from .base_config import BaseConfig
from .multi_line_formatter import MultiLineFormatter


class BaseLogger:
    """Configure a named logger and delegate standard logging operations.

    Args:
        config: Console and optional file settings.
        _is_child: Internal flag for children sharing their parent's handlers.
    """

    CRITICAL = logging.CRITICAL
    FATAL = logging.FATAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    WARN = logging.WARN
    INFO = logging.INFO
    DEBUG = logging.DEBUG
    NOTSET = logging.NOTSET

    def __init__(self, config: BaseConfig | None = None, _is_child: bool = False):
        """Prepare handlers only on the named logger's first setup.

        Args:
            config: Logging settings reused by child loggers.
            _is_child: Whether handlers should be left to the parent.
        """
        self.config = config if config is not None else BaseConfig()
        self._logger = logging.getLogger(self.config.name)
        self._handlers: list[logging.Handler] = []

        if not _is_child and not getattr(self._logger, "_assistant_configured", False):
            self._configure()

    def _configure(self) -> None:
        """Attach this instance's handlers to its named logger."""
        self._logger.setLevel(self.config.level)
        self._logger.propagate = self.config.propagate

        if self.config.console_log:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(self.config.console_log_level)
            use_color = self.config.console_log_color and sys.stderr.isatty()
            console_handler.setFormatter(self._formatter(use_color))
            self._logger.addHandler(console_handler)
            self._handlers.append(console_handler)

        if self.config.file_log:
            self.config.file_log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                self.config.file_log_path,
                mode=self.config.file_log_mode,
                encoding=self.config.file_log_encoding,
            )
            file_handler.setLevel(self.config.file_log_level)
            file_handler.setFormatter(self._formatter(use_color=False))
            self._logger.addHandler(file_handler)
            self._handlers.append(file_handler)

        setattr(self._logger, "_assistant_configured", True)

    def _formatter(self, use_color: bool) -> MultiLineFormatter:
        """Build a consistent formatter for a console or file handler.

        Args:
            use_color: Whether the output supports ANSI colors.

        Returns:
            Formatter with aligned multiline messages.
        """
        formatter = MultiLineFormatter(
            fmt=self.config.fmt,
            datefmt=self.config.date_fmt,
            style=self.config.style,
            use_color=use_color,
            additional_indent=self.config.multi_line_indent,
        )
        return formatter

    @property
    def name(self) -> str:
        """Return the logger's hierarchical name."""
        name = self._logger.name
        return name

    @property
    def level(self) -> int:
        """Return the configured severity threshold."""
        level = self._logger.level
        return level

    def get_child(self, suffix: str = "sub") -> Self:
        """Create a child sharing the parent's handlers and effective level.

        Args:
            suffix: Name appended to the parent's logger name.

        Returns:
            Logger wrapper forwarding records to this parent.
        """
        child = self.__class__(config=self.config, _is_child=True)
        child._logger = self._logger.getChild(suffix)
        child._logger.propagate = True
        return child

    def close(self) -> None:
        """Close this wrapper's handlers, leaving reused parent handlers intact."""
        if not self._handlers:
            return

        for handler in self._handlers:
            self._logger.removeHandler(handler)
            handler.close()

        self._handlers.clear()
        setattr(self._logger, "_assistant_configured", False)

    def __getattr__(self, item: str) -> Any:
        """Delegate methods such as info, debug and exception to logging.Logger.

        Args:
            item: Standard logging attribute requested by the caller.

        Returns:
            Attribute of the wrapped standard logger.
        """
        attribute = getattr(self._logger, item)
        return attribute

    def __repr__(self) -> str:
        """Return the logger name and configured severity for inspection."""
        description = (
            f"<{type(self).__name__} name={self.name!r} "
            f"level={logging.getLevelName(self.level)}>"
        )
        return description
