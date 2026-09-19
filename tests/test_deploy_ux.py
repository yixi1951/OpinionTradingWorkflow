from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_run_ui_sh_mirrors_windows_defaults():
    text = (ROOT / "scripts" / "run_ui.sh").read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "PYTHONPATH" in text
    assert ".venv" in text
    assert "streamlit run src/opinion_trading/ui_dashboard.py" in text
    assert "--port" in text
    assert "--no-browser" in text
    assert "8501" in text


def test_docker_compose_documents_streamlit_ui():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "streamlit-ui" in text
    assert "8501:8501" in text
    assert "ui_dashboard.py" in text
    assert "./data:/app/data" in text
    assert "--profile ui" in text
    # Full stack ports stay documented
    assert "8000:8000" in text
