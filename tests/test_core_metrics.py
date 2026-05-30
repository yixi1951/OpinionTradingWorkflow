from opinion_trading.core.metrics import compute_performance_metrics


def test_metrics_empty():
    out = compute_performance_metrics([])
    assert out["annual_return"] == 0.0
    assert out["max_drawdown"] == 0.0
    assert out["sharpe"] == 0.0


def test_metrics_simple_growth():
    eq = [100.0, 110.0, 121.0]
    out = compute_performance_metrics(eq)
    assert out["final_equity"] == 121.0
    assert out["max_drawdown"] == 0.0
    assert out["annual_return"] > 0


def test_metrics_drawdown_and_sharpe():
    eq = [100.0, 90.0, 95.0, 80.0]
    out = compute_performance_metrics(eq)
    assert 0.0 <= out["max_drawdown"] <= 1.0
    assert out["final_equity"] == 80.0
