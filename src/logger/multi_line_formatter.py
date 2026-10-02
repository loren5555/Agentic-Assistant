"""Align multiline log messages and optionally color console output."""

import logging
import textwrap
from typing import Literal


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
        additional_indent: int = 0
    ):
        """Set the record format and multiline appearance.

        Args:
            fmt: Standard logging record format.
            datefmt: Timestamp format.
            style: Syntax used by the format string.
            validate: Whether logging validates the format string.
            use_color: Whether to add ANSI severity colors.
            additional_indent: Extra spaces before continuation lines.
        """
        super().__init__(fmt, datefmt, style, validate=validate)
        self.use_color = use_color
        self.additional_indent = additional_indent

    def format(self, record: logging.LogRecord) -> str:
        """Format a record with continuation lines aligned to its message.

        Args:
            record: Message, severity and metadata supplied by logging.

        Returns:
            Formatted message, optionally decorated with ANSI colors.
        """
        # Inject {shortname}: last segment of the dotted logger name.
        # e.g. "assistant.codex.router" -> "router".
        record.shortname = record.name.rsplit('.', 1)[-1]
        
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
