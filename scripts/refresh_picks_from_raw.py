"""Refresh realtime_picks CSV from merged OpenClaw-scored raw posts."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def _load_merged_raw(raw_dir: Path) -> pd.DataFrame:
    files = sorted(raw_dir.glob("raw_posts_*.csv"), key=lambda p: p.name)
    frames = []
    for path in files:
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    if "url" in out.columns:
        out = out.drop_duplicates(subset=["url"], keep="last")
    return out


def main() -> None:
    raw = _load_merged_raw(Path("data/raw"))
    if raw.empty:
        raise SystemExit("no raw_posts_*.csv under data/raw")
    raw["ai_score"] = pd.to_numeric(raw.get("ai_score"), errors="coerce")
    raw = raw.dropna(subset=["symbol", "ai_score"])
    plat = raw.groupby(["symbol", "platform"], as_index=False)["ai_score"].mean()
    rows = []
    for symbol, g in plat.groupby("symbol"):
        ps = ", ".join(
            f"{r.platform}:{r.ai_score:.3f}"
            for _, r in g.sort_values("platform").iterrows()
        )
        rows.append(
            {
                "symbol": symbol,
                "avg_score": round(float(g["ai_score"].mean()), 4),
                "platform_scores": ps,
                "samples": int(len(raw[raw["symbol"] == symbol])),
            }
        )
    out = pd.DataFrame(rows).sort_values("avg_score", ascending=False)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = Path(f"data/reports/realtime_picks_{ts}.csv")
    md_path = Path(f"data/reports/realtime_picks_{ts}.md")
    out.to_csv(csv_path, index=False)
    lines = [
        "# Realtime AI Picks - merged raw_posts (OpenClaw)",
        "",
        f"Source rows: {len(raw)} | symbols: {len(out)}",
        "",
        "## Top Picks",
    ]
    for i, r in enumerate(out.itertuples(index=False), 1):
        lines.append(
            f"- #{i} {r.symbol} | avg_score={r.avg_score} | samples={r.samples} | {r.platform_scores}"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", csv_path, "rows", len(out), "from_raw", len(raw))
    print(out.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
