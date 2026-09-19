"""Tests for the shared logging module (log_utils.py)."""

from __future__ import annotations

import logging

from opinion_trading.core.log_utils import configure_logging, get_logger, reset_logging


def setup_function():
    """Reset logging before each test to ensure clean state."""
    reset_logging()


def test_get_logger_returns_logger():
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"


def test_configure_logging_respects_env_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging(level="DEBUG")
    logger = get_logger("test_level")
    assert logger.isEnabledFor(logging.DEBUG)


def test_configure_logging_file_output(tmp_path):
    log_file = str(tmp_path / "test.log")
    configure_logging(level="DEBUG", log_file=log_file)
    logger = get_logger("test_file")
    logger.info("hello world")

    # Flush and close all handlers
    for handler in logging.getLogger().handlers[:]:
        handler.flush()
        handler.close()
        logging.getLogger().removeHandler(handler)

    content = tmp_path.joinpath("test.log").read_text("utf-8")
    assert "hello world" in content
    assert "INFO" in content


def test_configure_logging_default_level():
    configure_logging()
    logger = get_logger("test_default")
    assert logger.isEnabledFor(logging.INFO)
    assert not logger.isEnabledFor(logging.DEBUG)  # default INFO


def test_idempotent_configure():
    """Calling configure_logging twice should not raise."""
    configure_logging()
    configure_logging()  # second call is no-op
    logger = get_logger("test_idempotent")
    assert isinstance(logger, logging.Logger)
