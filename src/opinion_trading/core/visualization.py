from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Tuple


def load_backtest_csv(file_path: str) -> List[dict]:
    rows: List[dict] = []
    with Path(file_path).open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def plot_sharpe_vs_threshold(rows: List[dict], output_path: str) -> None:
    if not rows:
        return

    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ModuleNotFoundError("matplotlib is required. Install with: pip install -r requirements.txt") from exc

    x: List[float] = []
    y: List[float] = []
    labels: List[str] = []

    for row in rows:
        x.append(float(row["bearish_threshold"]))
        y.append(float(row["sharpe"]))
        labels.append(row["platforms"])

    plt.figure(figsize=(10, 6))
    plt.scatter(x, y, alpha=0.8)
    plt.title("Sharpe Ratio vs Bearish Threshold")
    plt.xlabel("Bearish Threshold")
    plt.ylabel("Sharpe Ratio")
    plt.grid(alpha=0.25)

    top_idx = sorted(range(len(y)), key=lambda i: y[i], reverse=True)[:5]
    for i in top_idx:
        plt.annotate(labels[i], (x[i], y[i]), fontsize=8)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(target, dpi=180)
    plt.close()


def top_n_table(rows: List[dict], n: int = 10) -> List[Tuple[str, float, float, float]]:
    sorted_rows = sorted(rows, key=lambda r: float(r["sharpe"]), reverse=True)[:n]
    return [
        (
            row["platforms"],
            float(row["annual_return"]),
            float(row["max_drawdown"]),
            float(row["sharpe"]),
        )
        for row in sorted_rows
    ]
