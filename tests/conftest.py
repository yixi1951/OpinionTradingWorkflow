import os
import sys
from pathlib import Path

import pytest

# Add project root to sys.path to allow importing run_pipeline
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def _block_live_deepseek(monkeypatch):
    """CI / default pytest never call DeepSeek. Tests that need a key mock HTTP."""
    if os.environ.get("DEEPSEEK_ALLOW_LIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
