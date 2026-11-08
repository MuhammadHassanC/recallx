"""Structured logging infrastructure for RecallX."""

from __future__ import annotations

import logging
import sys
from typing import Any

# Check for rich logging availability
try:
    from rich.logging import RichHandler

    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

_DEFAULT_LOGGER_NAME = "recallx"
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_level(level: str | int) -> int:
    """Normalize and resolve a logging level.

    Args:
        level: String level name (e.g., 'DEBUG', 'info') or integer level.

    Returns:
        Standard logging level integer.
    """
    if isinstance(level, int):
        return level

    normalized = level.strip().upper()
    level_map = {
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }
    return level_map.get(normalized, logging.WARNING)


def setup_logging(
    level: str | int = "WARNING",
    *,
    json_format: bool = False,
    quiet: bool = False,
) -> None:
    """Configure structured logging for RecallX.

    Configures the root and 'recallx' loggers using RichHandler when available,
    falling back to standard library StreamHandler.

    Args:
        level: Minimum logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR').
        json_format: Whether to output structured JSON logs instead of human text.
        quiet: If True, sets logging level to ERROR to suppress non-critical output.
    """
    target_level = logging.ERROR if quiet else _parse_level(level)
    root_logger = logging.getLogger()
    root_logger.setLevel(target_level)

    # Remove existing handlers to avoid duplicates on reconfiguration
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler: logging.Handler
    if json_format:
        # Standard stream handler with JSON formatting
        handler = logging.StreamHandler(sys.stderr)
        formatter = _JsonLogFormatter()
        handler.setFormatter(formatter)
    elif _HAS_RICH:
        # High-fidelity terminal logging with rich
        handler = RichHandler(
            level=target_level,
            show_time=True,
            show_level=True,
            show_path=False,
            rich_tracebacks=True,
            markup=False,
        )
    else:
        # Portable stdlib stream handler
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
        handler.setFormatter(formatter)

    handler.setLevel(target_level)
    root_logger.addHandler(handler)

    # Ensure recallx logger propagates cleanly
    recallx_logger = logging.getLogger(_DEFAULT_LOGGER_NAME)
    recallx_logger.setLevel(target_level)


class _JsonLogFormatter(logging.Formatter):
    """Minimal stdlib JSON formatter for structured machine logs."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        log_obj: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_text:
            log_obj["exception"] = record.exc_text
        elif record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


def get_logger(name: str = _DEFAULT_LOGGER_NAME) -> logging.Logger:
    """Obtain a logger instance configured within the RecallX hierarchy.

    Args:
        name: Sub-logger name (e.g. 'recallx.storage', 'recallx.search').

    Returns:
        Configured logging.Logger instance.
    """
    if not name.startswith("recallx") and name != "":
        name = f"recallx.{name}"
    return logging.getLogger(name)
