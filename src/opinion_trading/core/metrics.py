from __future__ import annotations

import math
from typing import Dict, List


def compute_performance_metrics(equity_curve: List[float]) -> Dict[str, float]:
    if not equity_curve:
        return {
            "annual_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "final_equity": 0.0,
        }

    if len(equity_curve) == 1:
        return {
            "annual_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "final_equity": equity_curve[-1],
        }

    returns: List[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        curr = equity_curve[i]
        if prev <= 0:
            returns.append(0.0)
        else:
            returns.append((curr / prev) - 1)

    start = equity_curve[0]
    end = equity_curve[-1]
    n_days = len(equity_curve)

    if start <= 0:
        annual_return = 0.0
    else:
        annual_return = (end / start) ** (252 / max(1, n_days - 1)) - 1

    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak if peak > 0 else 0.0
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    if returns:
        mean_ret = sum(returns) / len(returns)
        var = sum((x - mean_ret) ** 2 for x in returns) / len(returns)
        std = math.sqrt(var)
        sharpe = (mean_ret / std) * math.sqrt(252) if std > 0 else 0.0
    else:
        sharpe = 0.0

    return {
        "annual_return": annual_return,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "final_equity": end,
    }
