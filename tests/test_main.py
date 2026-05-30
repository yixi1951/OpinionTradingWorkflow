import sys

from opinion_trading import main as main_module


def test_parse_args_defaults(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog"])
    args = main_module.parse_args()
    assert args.mode == "daily"


def test_run_pipeline_imports():
    # ensure run_pipeline can be imported without executing main
    import run_pipeline

    assert hasattr(run_pipeline, "PROJECT_ROOT")
