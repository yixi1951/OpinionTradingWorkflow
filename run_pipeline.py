"""Pipeline entrypoint with graceful shutdown support."""

from __future__ import annotations

import signal
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from opinion_trading.core.log_utils import configure_logging, get_logger
from opinion_trading.main import main  # noqa: E402

logger = get_logger(__name__)

_shutdown_requested = False


def _handle_sigterm(signum: int, frame: object) -> None:
    """Graceful shutdown: set flag so main loop can exit cleanly."""
    global _shutdown_requested
    if _shutdown_requested:
        logger.warning("Forced exit on second SIGTERM/SIGINT")
        sys.exit(1)
    _shutdown_requested = True
    logger.info("Shutdown requested (SIGTERM=%d), finishing current cycle...", signum)


def is_shutdown_requested() -> bool:
    """Check if a shutdown signal was received (for long-running loops)."""
    return _shutdown_requested


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    configure_logging()
    logger.info("Pipeline starting (PID=%d)", signal.thread_info() if hasattr(signal, "thread_info") else 0)
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(0)
    except Exception:
        logger.exception("Pipeline crashed with unhandled exception")
        sys.exit(1)
    logger.info("Pipeline completed successfully")
