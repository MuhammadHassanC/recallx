"""Tests for structured logging setup."""

from __future__ import annotations

import logging

from recallx.utils.logging import get_logger, setup_logging


def test_setup_logging_levels() -> None:
    setup_logging(level="DEBUG")
    logger = get_logger("test")
    assert logger.isEnabledFor(logging.DEBUG)

    setup_logging(level="ERROR")
    assert not logger.isEnabledFor(logging.INFO)
    assert logger.isEnabledFor(logging.ERROR)


def test_setup_logging_quiet() -> None:
    setup_logging(level="DEBUG", quiet=True)
    logger = get_logger("quiet_test")
    assert not logger.isEnabledFor(logging.INFO)
    assert logger.isEnabledFor(logging.ERROR)


def test_setup_logging_json() -> None:
    setup_logging(level="INFO", json_format=True)
    logger = get_logger("json_test")
    assert logger.name == "recallx.json_test"
