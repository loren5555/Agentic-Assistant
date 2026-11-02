"""Render readable progress or verbose diagnostics without changing log records.

Input origin:
    Shared logging handlers supply records with a current operation, a business
    message, and optional structured details or exception information.

Output destination:
    Console/file output shows the operation and business message by default.
    Verbose formatters append diagnostic fields and the full exception chain.

Boundaries:
    Details are explicitly supplied by callers, not extracted from rendered
    message text. Each handler formats a copy, allowing different verbosity
    without losing metadata or mutating another handler's message/traceback.
"""

import logging
import textwrap
from copy import copy
import json
from typing import Literal

from .call_context import current_call_path, current_operation


# ANSI Colors for different log levels
COLORS = {
    # Foreground Colors
    'BLACK':    '\x1b[30m',
    'BOLD_BLACK': '\x1b[30;1m',
    'GREY':     '\x1b[38;20m',
    'GREEN':    '\x1b[32m',
    'YELLOW':   '\x1b[33m',
    'RED':      '\x1b[31m',
    'BOLD_RED': '\x1b[31;1m',
    'WHITE':    '\x1b[37m',

    # Background Colors
    'BG_BLACK':   '\x1b[40m',
    'BG_RED':     '\x1b[41m',
    'BG_GREEN':   '\x1b[42m',
    'BG_YELLOW':  '\x1b[43m',
    'BG_BLUE':    '\x1b[44m',
    'BG_MAGENTA': '\x1b[45m',
    'BG_CYAN':    '\x1b[46m',
    'BG_WHITE':   '\x1b[47m',
    
    'RESET':    '\x1b[0m',
}


# Mapping of log levels to colors
LEVEL_COLORS = {
    logging.DEBUG: COLORS['GREY'],
    logging.INFO: COLORS['GREEN'],
    logging.WARNING: COLORS['YELLOW'],
    logging.ERROR: COLORS['RED'],
    logging.CRITICAL: COLORS['BOLD_BLACK'] + COLORS['BG_WHITE']
}


class MultiLineFormatter(logging.Formatter):
    """
    A custom logging.Formatter that handles multi-line messages gracefully.
    The first line of a multi-line message gets the full log prefix.
    Subsequent lines are indented to align with the message content of the first line,
    without repeating the full prefix.
    """
    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal['%', '{', '$'] = '{',
        validate: bool = True,
        use_color: bool = False,
        additional_indent: int = 0,
        verbose: bool = False,
    ):
        """Set the record format and multiline appearance.

        Args:
            fmt: Standard logging record format.
            datefmt: Timestamp format.
            style: Syntax used by the format string.
            validate: Whether logging validates the format string.
            use_color: Whether to add ANSI severity colors.
            additional_indent: Extra spaces before continuation lines.
            verbose: Whether to show diagnostic fields and exception tracebacks.
        """
        super().__init__(fmt, datefmt, style, validate=validate)
        self.use_color = use_color
        self.additional_indent = additional_indent
        self.verbose = verbose

    def formatException(self, exc_info) -> str:
        """Keep full exception chains behind verbose mode.

        Args:
            exc_info: Exception type, value, and traceback from the logging record.

        Returns:
            Full traceback in verbose mode, otherwise its type and a debug hint.
        """
        if self.verbose:
            text = super().formatException(exc_info)
        else:
            text = f"{exc_info[0].__name__}; use -v for diagnostic details."
        return text

    def format(self, record: logging.LogRecord) -> str:
        """Format a record with continuation lines aligned to its message.

        Args:
            record: Message, severity and metadata supplied by logging.

        Returns:
            Formatted message, optionally decorated with ANSI colors.
        """
        # A console/file handler may use different verbosity on the same record.
        # Never overwrite the original message or cache a traceback on it.
        record = copy(record)
        record.exc_text = None
        details = getattr(record, "details", None)
        if self.verbose and details:
            diagnostic = json.dumps(details, ensure_ascii=False, default=str)
            record.msg = record.getMessage() + "\nDetails: " + diagnostic
            record.args = ()

        # Inject {shortname}: last segment of the dotted logger name.
        # e.g. "assistant.codex.router" -> "router".
        record.shortname = record.name.rsplit('.', 1)[-1]
        if not hasattr(record, "call_path"):
            record.call_path = current_call_path()
        if not hasattr(record, "operation"):
            operation = current_operation()
            record.operation = operation if operation != "-" else record.name.removeprefix("assistant.")

        # Indent semantic layers, not the number of nested calls: subworkflows
        # remain readable and component/tool details never drift further right.
        kind = record.operation.partition(":")[0]
        indentation = {"step": 1, "component": 2, "tool": 2}.get(kind, 0)
        record.operation = "    " * indentation + record.operation
        
        formatted_message = super().format(record).split('\n')
        
        first_line = formatted_message[0]  # Get the formatted first line

        color = LEVEL_COLORS.get(record.levelno, COLORS['RESET']) if self.use_color else ''
        reset_color = COLORS['RESET'] if self.use_color else ''

        if len(formatted_message) > 1:
            # Calculate the indentation based on the length of the prefix
            # This is the length of the formatted first line minus the length of the actual message part
            message_first_line = record.message.split('\n')[0]
            header_index = first_line.rfind(message_first_line)
            if header_index == -1:
                header_length = len(first_line) - len(message_first_line)
            else:
                header_length = header_index

            # Use textwrap.indent to add the indentation to the rest of the message
            remaining_lines = '\n'.join(formatted_message[1:])
            indented_remaining_lines = textwrap.indent(remaining_lines, (header_length + self.additional_indent) * ' ')

            # Combine the formatted first line with the indented subsequent lines
            formatted_message = f"{first_line}\n{indented_remaining_lines}"
        else:
            # If there's only one line, just use it as is
            formatted_message = first_line

        colored_lines = [
            f"{color}{line}{reset_color}" for line in formatted_message.split('\n')
        ]
        colored_message = '\n'.join(colored_lines)

        return colored_message
