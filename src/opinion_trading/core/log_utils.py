"""Shared logging setup for the opinion_trading project.

Usage:
    from opinion_trading.core.log_utils import get_logger

    logger = get_logger(__name__)
    logger.info("pipeline started")
    logger.warning("OpenClaw unavailable, falling back to keyword")
    logger.error("collector failed", exc_info=True)
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_CONFIGURED = False
"""Reset this flag between tests via ``reset_logging()``."""


def reset_logging() -> None:
    """Reset logging configuration (for testing only)."""
    global _LOG_CONFIGURED
    _LOG_CONFIGURED = False


def configure_logging(
    *,
    level: str | None = None,
    log_dir: str | None = None,
    log_file: str | None = None,
) -> None:
    """Configure root logger once.  Safe to call multiple times (idempotent)."""
    global _LOG_CONFIGURED
    if _LOG_CONFIGURED:
        return

    level_str = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, level_str, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers: list[logging.Handler] = []

    # Console handler (stderr)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    handlers.append(console)

    # File handler (optional, with rotation)
    log_path = log_file
    if log_path is None and log_dir:
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        log_path = str(log_dir_path / "opinion_trading.log")
    if log_path:
        max_bytes = int(os.environ.get("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10MB
        backup_count = int(os.environ.get("LOG_BACKUP_COUNT", "5"))
        file_handler = RotatingFileHandler(
            log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    _LOG_CONFIGURED = True

    # Capture root logger warnings
    logging.basicConfig(level=log_level, handlers=handlers, force=True)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the given module name.

    Auto-configures if not yet configured (lazy init).
    """
    if not _LOG_CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
