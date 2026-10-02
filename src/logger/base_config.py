"""Console and optional local-file settings for assistant logging."""

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass
class BaseConfig:
    """Configure readable process logs without creating handlers or files.

    Attributes:
        name: Root logger name shared by its child loggers.
        level: Minimum severity accepted by the logger.
        style: Standard logging format syntax.
        fmt: Record format, including the final segment of the logger name.
        date_fmt: Timestamp format.
        console_log: Whether to print to stderr.
        console_log_level: Console severity threshold.
        console_log_color: Whether to use colors when stderr is a terminal.
        file_log: Whether to also write a plain-text log file.
        file_log_dir: Local directory used for file logging.
        file_log_name: Name of the optional log file.
        file_log_path: Derived path of the optional log file.
        file_log_mode: File opening mode.
        file_log_encoding: File text encoding.
        file_log_level: File severity threshold.
        propagate: Whether to forward records to ancestor loggers.
        multi_line_indent: Extra indentation for message continuation lines.
    """

    name: str = "assistant"
    level: int | str = logging.INFO
    style: Literal["%", "{", "$"] = "{"
    fmt: str = "{asctime} | {levelname:<8} | {name:<10} | {message}"
    date_fmt: str = "%H:%M:%S"

    console_log: bool = True
    console_log_level: int | str = logging.NOTSET
    console_log_color: bool = True

    file_log: bool = False
    file_log_mode: str = "a"
    file_log_encoding: str = "utf-8"
    file_log_level: int | str = logging.NOTSET
    file_log_dir: Path | str = ".agents/logs"
    file_log_name: str = "assistant.log"
    file_log_path: Path = field(init=False)

    propagate: bool = False
    multi_line_indent: int = 0

    def __post_init__(self) -> None:
        """Resolve the configured directory and file name into a path."""
        self.file_log_dir = Path(self.file_log_dir)
        self.file_log_path = self.file_log_dir / self.file_log_name

    def asdict(self) -> dict[str, Any]:
        """Return all settings, including the derived log-file path.

        Returns:
            Configuration fields as a dictionary.
        """
        settings = asdict(self)
        return settings
