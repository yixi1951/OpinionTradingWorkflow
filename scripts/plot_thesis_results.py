"""Publication-style thesis result figures (verify → score → test).

Outputs PNGs under data/reports/figures/ and optionally /opt/cursor/artifacts/.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[1]

# Academic palette — ink / slate / teal / amber (avoid purple AI defaults)
INK = "#1a1a1a"
SLATE = "#4a5568"
TEAL = "#0f6e6e"
TEAL_SOFT = "#d8ecec"
AMBER = "#b45309"
AMBER_SOFT = "#f3e7d3"
STEEL = "#334e68"
LINE = "#cbd5e1"
PAPER = "#fbfaf7"

MEASURE_ORDER = ["sent_llm", "bullishness", "sent_dict", "sent_mean", "sent_inf"]
MEASURE_LABEL = {
    "sent_llm": "Q4  LLM (Jev/DS)",
    "bullishness": "Q5  Bullishness",
    "sent_dict": "Q3  Dictionary",
    "sent_mean": "Q1  Mean",
    "sent_inf": "Q2  Influence-wt",
}
SOURCE_COLORS = {
    "jev": TEAL,
    "deepseek": STEEL,
    "cursor_llm": AMBER,
    "keyword": "#94a3b8",
    "pending_llm": "#cbd5e1",
}


def _setup_style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": PAPER,
            "axes.facecolor": PAPER,
            "savefig.facecolor": PAPER,
            "axes.edgecolor": LINE,
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": SLATE,
            "ytick.color": SLATE,
            "grid.color": LINE,
            "grid.linewidth": 0.6,
            "grid.alpha": 0.85,
            "font.size": 10.5,
            "axes.titlesize": 13,
            "axes.titleweight": "semibold",
            "axes.labelsize": 10.5,
            "legend.fontsize": 9,
            "figure.dpi": 140,
            "savefig.dpi": 220,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.unicode_minus": False,
        }
    )
    # Prefer CJK fonts when present
    from matplotlib import font_manager

    for name in (
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "WenQuanYi Micro Hei",
        "SimHei",
        "DejaVu Sans",
    ):
        if any(name.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
            mpl.rcParams["font.family"] = "sans-serif"
            mpl.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            break


def _load_tables(report_dir: Path):
    fm = pd.read_csv(report_dir / "thesis_fama_macbeth.csv")
    logit = pd.read_csv(report_dir / "thesis_logit.csv")
    panel = pd.read_csv(report_dir / "sentiment_panel.csv")
    return fm, logit, panel


def _score_source_counts(raw_dir: Path) -> pd.Series:
    counts: Dict[str, int] = {}
    for path in sorted(raw_dir.glob("raw_posts_*.csv")):
        try:
            df = pd.read_csv(path, usecols=lambda c: c == "score_source")
        except Exception:
            continue
        if "score_source" not in df.columns:
            continue
        vc = df["score_source"].fillna("keyword").astype(str).value_counts()
        for k, v in vc.items():
            counts[str(k)] = counts.get(str(k), 0) + int(v)
    return pd.Series(counts).sort_values(ascending=True)


def fig_pipeline(out: Path) -> None:
    fig, ax = plt.subplots(figsize=(11.2, 2.9))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3)
    ax.axis("off")
    steps = [
        (0.35, "A · Crawl", "Guba UGC"),
        (2.55, "B · Verify", "OpenClaw free model"),
        (4.75, "C · Score", "Jev → DeepSeek"),
        (6.95, "D · Aggregate", "Q4 / Q5 (+Q3)"),
        (9.15, "E · Test", "FM + Logit"),
    ]
    for i, (x, title, sub) in enumerate(steps):
        box = FancyBboxPatch(
            (x, 0.85),
            1.95,
            1.45,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            linewidth=1.2,
            edgecolor=TEAL if i in (1, 2) else STEEL,
            facecolor=TEAL_SOFT if i in (1, 2) else "#eef2f6",
            mutation_aspect=0.8,
        )
        ax.add_patch(box)
        ax.text(x + 0.975, 1.75, title, ha="center", va="center", fontsize=11, fontweight="semibold", color=INK)
        ax.text(x + 0.975, 1.25, sub, ha="center", va="center", fontsize=9, color=SLATE)
        if i < len(steps) - 1:
            ax.annotate(
                "",
                xy=(steps[i + 1][0] - 0.05, 1.55),
                xytext=(x + 2.0, 1.55),
                arrowprops=dict(arrowstyle="-|>", color=STEEL, lw=1.4, mutation_scale=12),
            )
    ax.text(0.35, 2.55, "Thesis pipeline", fontsize=14, fontweight="semibold", color=INK)
    ax.text(0.35, 0.35, "Verify → Score → Test   ·   keywords / influence weights are not formal scorers", fontsize=8.5, color=SLATE)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_coverage(counts: pd.Series, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), gridspec_kw={"width_ratios": [1.15, 1]})
    # left: stacked composition excluding keyword dominance via dual view
    llm = counts.reindex(["jev", "deepseek", "cursor_llm"]).fillna(0)
    other = float(counts.get("keyword", 0) + counts.get("pending_llm", 0))
    ax = axes[0]
    total = float(counts.sum()) or 1.0
    # donut
    sizes = [float(llm.sum()), other]
    colors = [TEAL, "#d0d7de"]
    wedges, _ = ax.pie(
        sizes,
        colors=colors,
        startangle=90,
        wedgeprops=dict(width=0.42, edgecolor=PAPER, linewidth=2),
    )
    ax.text(0, 0.08, f"{llm.sum():,.0f}", ha="center", va="center", fontsize=18, fontweight="semibold", color=TEAL)
    ax.text(0, -0.22, "LLM-scored", ha="center", va="center", fontsize=9, color=SLATE)
    ax.set_title("Formal vs placeholder coverage", pad=10)
    # legend manual
    ax.legend(
        wedges,
        [f"Jev/DeepSeek/cursor  {llm.sum():,.0f}", f"keyword/pending  {other:,.0f}"],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
        frameon=False,
    )

    ax = axes[1]
    llm_only = llm[llm > 0]
    y = np.arange(len(llm_only))
    bars = ax.barh(
        y,
        llm_only.values,
        color=[SOURCE_COLORS.get(k, STEEL) for k in llm_only.index],
        height=0.55,
        edgecolor="none",
    )
    ax.set_yticks(y)
    ax.set_yticklabels([str(k) for k in llm_only.index])
    ax.set_xlabel("Posts")
    ax.set_title("LLM scorer breakdown")
    for b, v in zip(bars, llm_only.values):
        ax.text(v + max(llm_only.values) * 0.02, b.get_y() + b.get_height() / 2, f"{int(v):,}", va="center", fontsize=9, color=SLATE)
    ax.set_xlim(0, max(llm_only.values) * 1.22 if len(llm_only) else 1)
    fig.suptitle("Score-source coverage", fontsize=14, fontweight="semibold", y=1.02)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_fm_forest(fm: pd.DataFrame, out: Path) -> None:
    focus = fm[fm["measure"].isin(MEASURE_ORDER)].copy()
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 4.6), sharey=True)
    for ax, h in zip(axes, [1, 3, 5]):
        sub = focus[focus["horizon"] == h].set_index("measure").reindex(MEASURE_ORDER)
        y = np.arange(len(sub))[::-1]
        coef = sub["coef_mean"].astype(float).values
        se = sub["coef_se"].astype(float).values
        t = sub["t_stat"].astype(float).values
        # band
        ax.axvspan(-1e9, 0, color="#f1f5f9", zorder=0)
        ax.axvline(0, color=INK, lw=0.9, zorder=1)
        colors = [TEAL if abs(tt) >= 1.96 else STEEL for tt in t]
        ax.errorbar(
            coef,
            y,
            xerr=1.96 * se,
            fmt="o",
            color=STEEL,
            ecolor="#94a3b8",
            elinewidth=1.4,
            capsize=3.5,
            markersize=6.5,
            zorder=3,
        )
        for yi, c, col in zip(y, coef, colors):
            ax.scatter([c], [yi], s=42, color=col, zorder=4, edgecolors="white", linewidths=0.6)
        ax.set_yticks(y)
        ax.set_yticklabels([MEASURE_LABEL[m] for m in MEASURE_ORDER][::-1])
        ax.set_title(f"Horizon  h = {h}", fontsize=11)
        ax.set_xlabel("coef  ± 1.96 SE")
        # autoscale with padding
        finite = coef[np.isfinite(coef)]
        if len(finite):
            span = np.nanmax(np.abs(coef) + 1.96 * se)
            ax.set_xlim(-span * 1.15, span * 1.15)
        ax.grid(axis="x", zorder=0)
    fig.suptitle("Fama–MacBeth forest plot", fontsize=14, fontweight="semibold")
    fig.text(0.5, -0.02, "Teal marker: |t| ≥ 1.96   ·   Gray: not significant at 5%", ha="center", fontsize=8.5, color=SLATE)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_fm_heatmap(fm: pd.DataFrame, out: Path) -> None:
    focus = fm[fm["measure"].isin(MEASURE_ORDER)].copy()
    mat = focus.pivot(index="measure", columns="horizon", values="t_stat").reindex(MEASURE_ORDER)
    mat = mat[[c for c in [1, 3, 5] if c in mat.columns]]
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    cmap = LinearSegmentedColormap.from_list("teal_div", ["#7f1d1d", PAPER, TEAL])
    vmax = max(2.5, float(np.nanmax(np.abs(mat.values))))
    im = ax.imshow(mat.values, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(mat.shape[1]))
    ax.set_xticklabels([f"h={c}" for c in mat.columns])
    ax.set_yticks(range(mat.shape[0]))
    ax.set_yticklabels([MEASURE_LABEL[m] for m in mat.index])
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            val = mat.values[i, j]
            if np.isfinite(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=10, color=INK if abs(val) < vmax * 0.55 else "white", fontweight="medium")
    ax.set_title("Newey–West t-statistics heatmap", pad=10)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("t-stat")
    # significance guides
    ax.axhline(-0.5, color="none")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_logit_auc(logit: pd.DataFrame, out: Path) -> None:
    focus = logit[logit["measure"].isin(MEASURE_ORDER)].copy()
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    x = np.arange(len(MEASURE_ORDER))
    width = 0.24
    palette = {1: TEAL, 3: STEEL, 5: AMBER}
    for i, h in enumerate([1, 3, 5]):
        sub = focus[focus["horizon"] == h].set_index("measure").reindex(MEASURE_ORDER)
        vals = sub["auc"].astype(float).values
        bars = ax.bar(x + (i - 1) * width, vals, width, label=f"h={h}", color=palette[h], edgecolor="none")
        for b, v in zip(bars, vals):
            if np.isfinite(v):
                ax.text(b.get_x() + b.get_width() / 2, v + 0.004, f"{v:.3f}", ha="center", va="bottom", fontsize=7.5, color=SLATE)
    ax.axhline(0.5, color="#94a3b8", ls="--", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels([MEASURE_LABEL[m] for m in MEASURE_ORDER], rotation=12, ha="right")
    ax.set_ylabel("AUC")
    ymax = max(0.62, float(np.nanmax(focus["auc"])) + 0.04)
    ax.set_ylim(0.46, ymax)
    ax.set_title("Logit direction AUC by measure and horizon")
    ax.legend(frameon=False, ncol=3, loc="upper right")
    ax.grid(axis="y")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_llm_timeline(panel: pd.DataFrame, out: Path) -> None:
    if "n_llm_posts" not in panel.columns:
        return
    daily = (
        panel.assign(trade_date=pd.to_datetime(panel["trade_date"], errors="coerce"))
        .dropna(subset=["trade_date"])
        .groupby("trade_date", as_index=False)
        .agg(llm_posts=("n_llm_posts", "sum"), cells=("symbol", "count"), llm_cells=("n_llm_posts", lambda s: int((s > 0).sum())))
    )
    fig, ax = plt.subplots(figsize=(10.2, 3.9))
    ax.fill_between(daily["trade_date"], daily["llm_posts"], color=TEAL, alpha=0.18, linewidth=0)
    ax.plot(daily["trade_date"], daily["llm_posts"], color=TEAL, lw=1.8, label="LLM-scored posts / day")
    ax2 = ax.twinx()
    ax2.plot(daily["trade_date"], daily["llm_cells"] / daily["cells"].clip(lower=1), color=AMBER, lw=1.3, ls="--", label="Share of symbol-days with LLM")
    ax2.set_ylabel("LLM cell share", color=AMBER)
    ax2.tick_params(axis="y", colors=AMBER)
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color(AMBER)
    ax.set_ylabel("Posts")
    ax.set_title("Daily LLM coverage intensity")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, frameon=False, loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_score_scatter(raw_dir: Path, out: Path, max_points: int = 1200) -> None:
    frames: List[pd.DataFrame] = []
    for path in sorted(raw_dir.glob("raw_posts_*.csv")):
        try:
            df = pd.read_csv(path, usecols=lambda c: c in {"keyword_score", "ai_score", "score_source"})
        except Exception:
            continue
        if not {"keyword_score", "ai_score", "score_source"}.issubset(df.columns):
            continue
        df = df[df["score_source"].astype(str).isin(["jev", "deepseek"])]
        if not df.empty:
            frames.append(df)
    if not frames:
        return
    df = pd.concat(frames, ignore_index=True)
    if len(df) > max_points:
        df = df.sample(max_points, random_state=42)
    fig, ax = plt.subplots(figsize=(5.8, 5.4))
    for src, sub in df.groupby(df["score_source"].astype(str)):
        ax.scatter(
            pd.to_numeric(sub["keyword_score"], errors="coerce"),
            pd.to_numeric(sub["ai_score"], errors="coerce"),
            s=18,
            alpha=0.55,
            color=SOURCE_COLORS.get(src, STEEL),
            label=src,
            edgecolors="none",
        )
    ax.plot([-1, 1], [-1, 1], color="#94a3b8", ls="--", lw=1)
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel("keyword_score")
    ax.set_ylabel("LLM ai_score (Jev/DeepSeek)")
    ax.set_title("Dictionary vs LLM scores")
    ax.legend(frameon=False, loc="lower right")
    ax.set_aspect("equal")
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def write_pack_md(report_dir: Path, counts: pd.Series, fm: pd.DataFrame, logit: pd.DataFrame) -> None:
    llm = int(counts.reindex(["jev", "deepseek"]).fillna(0).sum())
    md = f"""# 实证成果包（高级配图）

流水线：**采集 → OpenClaw 验真 → Jev/DeepSeek 打分 → FM / Logit**。

当前正式 LLM 打分帖数：**{llm:,}**（jev={int(counts.get('jev',0)):,} · deepseek={int(counts.get('deepseek',0)):,}）。

## 图版

| 图 | 文件 | 内容 |
|----|------|------|
| 01 | `figures/fig01_pipeline.png` | 验真→打分→测评流水线 |
| 02 | `figures/fig02_coverage.png` | 打分覆盖（环形图 + LLM 细分） |
| 03 | `figures/fig03_fm_forest.png` | FM 森林图（±1.96 SE） |
| 04 | `figures/fig04_fm_tstat.png` | Newey–West t 热力图 |
| 05 | `figures/fig05_logit_auc.png` | Logit AUC 分组柱 |
| 06 | `figures/fig06_llm_timeline.png` | 日度 LLM 覆盖强度 |
| 07 | `figures/fig07_dict_vs_llm.png` | 词典分 vs LLM 分散点 |

## 主表摘要（Q4 sent_llm）

"""
    sub = fm[fm["measure"] == "sent_llm"].sort_values("horizon")
    md += "| h | coef | SE | t | n_obs |\n|---|------|----|---|-------|\n"
    for _, r in sub.iterrows():
        md += f"| {int(r.horizon)} | {r.coef_mean:.4f} | {r.coef_se:.4f} | {r.t_stat:.3f} | {int(r.n_obs)} |\n"
    md += "\n### Logit AUC\n\n| h | AUC | accuracy |\n|---|-----|----------|\n"
    for _, r in logit[logit["measure"] == "sent_llm"].sort_values("horizon").iterrows():
        md += f"| {int(r.horizon)} | {r.auc:.3f} | {r.accuracy:.3f} |\n"
    md += "\n> 样本级 LLM 覆盖下系数可能不显著；扩大 Jev/DS 后再作终表解读。检验可预测性，不声称因果。\n"
    (report_dir / "thesis_results_pack.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", default=str(ROOT / "data" / "reports"))
    parser.add_argument("--raw-dir", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--also-artifacts", action="store_true", default=True)
    args = parser.parse_args()
    _setup_style()
    report_dir = Path(args.report_dir)
    fig_dir = report_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    art = Path("/opt/cursor/artifacts")
    if args.also_artifacts:
        art.mkdir(parents=True, exist_ok=True)

    fm, logit, panel = _load_tables(report_dir)
    counts = _score_source_counts(Path(args.raw_dir))

    outs = {
        "fig01_pipeline.png": lambda p: fig_pipeline(p),
        "fig02_coverage.png": lambda p: fig_coverage(counts, p),
        "fig03_fm_forest.png": lambda p: fig_fm_forest(fm, p),
        "fig04_fm_tstat.png": lambda p: fig_fm_heatmap(fm, p),
        "fig05_logit_auc.png": lambda p: fig_logit_auc(logit, p),
        "fig06_llm_timeline.png": lambda p: fig_llm_timeline(panel, p),
        "fig07_dict_vs_llm.png": lambda p: fig_score_scatter(Path(args.raw_dir), p),
    }
    for name, fn in outs.items():
        path = fig_dir / name
        fn(path)
        if args.also_artifacts and path.exists():
            (art / name).write_bytes(path.read_bytes())
        print("wrote", path)

    write_pack_md(report_dir, counts, fm, logit)
    if args.also_artifacts:
        (art / "thesis_results_pack.md").write_text((report_dir / "thesis_results_pack.md").read_text(encoding="utf-8"), encoding="utf-8")
    print("pack", report_dir / "thesis_results_pack.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
