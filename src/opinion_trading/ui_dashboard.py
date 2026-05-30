from __future__ import annotations

import glob
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from opinion_trading.core.evaluation import evaluate_signals, load_prices, normalize_price_frame
from opinion_trading.core.monthly_training import (
    build_monthly_training_frame,
    fetch_prices_with_timeout,
    load_latest_monthly_training,
    load_training_history,
    save_monthly_training_report,
)


# Simple i18n dictionary for UI text
LANG = {
    "en": {
        "page_title": "OpenClaw AI Picks",
        "header_title": "OpenClaw AI Picks Dashboard",
        "report_dir": "Report directory",
        "raw_dir": "Raw data directory",
        "memory_dir": "Memory directory",
        "quick_start": "Quick Start Tutorial",
        "tutorial_markdown": """
**Step 1**: Run realtime mode to generate picks and alerts.  
**Step 2**: Run daily mode to generate raw posts and explanations.  
**Step 3**: Open this UI to see picks, platform drivers, and accuracy.  

**Expected outputs**:
- realtime picks CSV/MD in data/reports
- alerts JSONL in data/reports and data/memory
- raw posts CSV in data/raw
""",
        "realtime_picks": "Realtime Picks",
        "no_realtime_picks": "No realtime picks found. Run realtime mode first.",
        "score_alerts": "Score Alerts",
        "no_alerts": "No alert file found or no alerts triggered.",
        "sentiment_trend": "Sentiment Trend (by platform)",
        "no_sentiment_history": "No sentiment history found.",
        "platform_contribution": "Platform Contribution (Pick Explanation)",
        "select_symbol_for_contribution": "Select symbol for contribution",
        "platform_radar": "Platform Radar (Sentiment Contrast)",
        "select_symbol_for_radar": "Select symbol for radar",
        "top_comments": "Why this pick? (Top comments)",
        "no_raw_posts": "No raw post CSV found. Run daily mode first.",
        "pick_reason_cards": "Pick Reason Cards",
        "run_realtime_daily_first": "Run realtime mode and daily mode first to see pick cards.",
        "evaluation": "Accuracy & Cost Performance (Months)",
        "price_source": "Price source",
        "price_options": ["Local CSV path", "Upload CSV", "Yahoo fallback"],
        "upload_label": "Upload price CSV (date,symbol,close)",
        "local_csv_path": "Local CSV path (date,symbol,close)",
        "save_uploaded": "Save uploaded CSV to local cache",
        "uploaded_invalid": "Uploaded price CSV could not be parsed. Please use columns: date,symbol,close",
        "start_date": "Start date (YYYY-MM-DD)",
        "end_date": "End date (YYYY-MM-DD)",
        "run_evaluation": "Run evaluation",
        "upload_required": "Please upload a valid price CSV before running evaluation.",
        "monthly_training": "Monthly Training & Forecast",
        "training_lookback": "Training lookback months",
        "refresh_monthly": "Refresh monthly training",
        "no_monthly_report": "No monthly training report found yet. Click Refresh monthly training after running daily/realtime mode.",
        "monthly_saved": "Monthly training saved",
        "language_label": "Language / 语言",
        "language_en": "English",
        "language_zh": "中文",
        "no_reason_cards": "No picks or raw posts available for reason cards.",
        "risk_balanced": "Balanced sentiment",
        "risk_high_negative": "High negative sentiment risk",
        "risk_weak_signal": "Weak sentiment signal",
        "positive_highlight": "Top Positive Comments",
        "negative_highlight": "Top Negative Comments",
        "key_fields": "Key fields",
        "kpi_label": "KPI",
        "score_label": "Score",
        "risk_hint_label": "Risk hint",
        "select_symbol": "Select symbol",
        "no_contribution_data": "No contribution data available.",
        "no_radar_data": "No radar data available.",
        "yahoo_need_dates": "Yahoo fallback needs start and end date.",
        "yahoo_no_prices": "Yahoo returned no prices. Use Upload CSV or Local CSV path.",
        "metric_forecast_success_rate": "Forecast success rate",
        "metric_rolling_success_rate": "Rolling success rate",
        "metric_latest_month_accuracy": "Latest month accuracy",
        "metric_forecast_direction": "Forecast direction",
        "coverage": "Coverage",
        "month": "Month",
        "rate": "Rate",
        "signal_count": "Signal Count",
        "uploaded_rows": "Uploaded rows",
        "symbols_count": "Symbols",
        "eval_accuracy": "Accuracy",
        "eval_avg_return": "Avg Return",
        "eval_win_rate": "Win Rate",
        "eval_sharpe_like": "Sharpe-like",
        "evaluation_failed": "Evaluation failed: {error}",
        "monthly_failed": "Monthly training failed: {error}",
        "valid_dates_missing": "Signal history is present but has no valid dates.",
        "empty_yahoo_prices": "empty Yahoo prices",
        "col_platform": "platform",
        "col_platform_score": "platform_score",
        "col_weight_pct": "weight_pct",
        "contribution_pct": "Contribution %",
        "col_title": "title",
        "col_summary": "summary",
        "col_ai_score": "ai_score",
        "col_url": "url",
    },
    "zh": {
        "page_title": "OpenClaw AI 选股",
        "header_title": "OpenClaw AI 选股仪表盘",
        "report_dir": "报告目录",
        "raw_dir": "原始数据目录",
        "memory_dir": "内存目录",
        "quick_start": "快速开始教程",
        "tutorial_markdown": """
**步骤 1**：运行实时模式以生成选股和告警。  
**步骤 2**：运行日线模式以生成原始帖子与解释。  
**步骤 3**：打开此界面查看选股、平台驱动和准确率。  

**期望输出**：
- data/reports 下的实时选股 CSV/MD
- data/reports 和 data/memory 下的告警 JSONL
- data/raw 下的原始帖子 CSV
""",
        "realtime_picks": "实时选股",
        "no_realtime_picks": "未找到实时选股。请先运行 realtime 模式。",
        "score_alerts": "评分告警",
        "no_alerts": "未找到告警文件或未触发告警。",
        "sentiment_trend": "情感趋势（按平台）",
        "no_sentiment_history": "未找到情感历史。",
        "platform_contribution": "平台贡献（选股解释）",
        "select_symbol_for_contribution": "选择用于贡献的代码",
        "platform_radar": "平台雷达（情感对比）",
        "select_symbol_for_radar": "选择雷达代码",
        "top_comments": "为何被选（Top 评论）",
        "no_raw_posts": "未找到原始帖子 CSV。请先运行 daily 模式。",
        "pick_reason_cards": "选股原因卡",
        "run_realtime_daily_first": "请先运行 realtime 与 daily 模式以查看选股卡。",
        "evaluation": "准确率与成本表现（月度）",
        "price_source": "价格来源",
        "price_options": ["本地 CSV 路径", "上传 CSV", "Yahoo 回退"],
        "upload_label": "上传价格 CSV（date,symbol,close）",
        "local_csv_path": "本地 CSV 路径（date,symbol,close）",
        "save_uploaded": "保存上传的 CSV 到本地缓存",
        "uploaded_invalid": "上传的价格 CSV 无法解析。请使用列：date,symbol,close",
        "start_date": "开始日期（YYYY-MM-DD）",
        "end_date": "结束日期（YYYY-MM-DD）",
        "run_evaluation": "运行评估",
        "upload_required": "请先上传有效的价格 CSV 再运行评估。",
        "monthly_training": "月度训练与预测",
        "training_lookback": "训练回溯月数",
        "refresh_monthly": "刷新月度训练",
        "no_monthly_report": "尚无月度训练报告。运行 daily/realtime 后点击刷新。",
        "monthly_saved": "月度训练已保存",
        "language_label": "Language / 语言",
        "language_en": "English",
        "language_zh": "中文",
        "no_reason_cards": "未找到用于生成原因卡的选股或原始帖子。",
        "risk_balanced": "情绪平衡",
        "risk_high_negative": "高度负面情绪风险",
        "risk_weak_signal": "信号较弱",
        "positive_highlight": "正面高亮评论",
        "negative_highlight": "负面高亮评论",
        "key_fields": "关键字段",
        "kpi_label": "KPI",
        "score_label": "分数",
        "risk_hint_label": "风险提示",
        "select_symbol": "选择代码",
        "no_contribution_data": "暂无平台贡献数据。",
        "no_radar_data": "暂无雷达数据。",
        "yahoo_need_dates": "Yahoo 回退需要开始和结束日期。",
        "yahoo_no_prices": "Yahoo 未返回价格。请使用上传 CSV 或本地 CSV。",
        "metric_forecast_success_rate": "预测成功率",
        "metric_rolling_success_rate": "滚动成功率",
        "metric_latest_month_accuracy": "最新月份准确率",
        "metric_forecast_direction": "预测方向",
        "coverage": "覆盖范围",
        "month": "月份",
        "rate": "比率",
        "signal_count": "信号数量",
        "uploaded_rows": "上传行数",
        "symbols_count": "代码数",
        "eval_accuracy": "准确率",
        "eval_avg_return": "平均收益",
        "eval_win_rate": "胜率",
        "eval_sharpe_like": "类夏普比",
        "evaluation_failed": "评估失败：{error}",
        "monthly_failed": "月度训练失败：{error}",
        "valid_dates_missing": "信号历史存在，但没有有效日期。",
        "empty_yahoo_prices": "Yahoo 价格为空",
        "col_platform": "平台",
        "col_platform_score": "平台分数",
        "col_weight_pct": "权重 %",
        "contribution_pct": "贡献 %",
        "col_title": "标题",
        "col_summary": "摘要",
        "col_ai_score": "AI 分数",
        "col_url": "链接",
    },
}

# additional translation keys
LANG["en"]["saved_uploaded_to"] = "Saved uploaded prices to {path}"
LANG["zh"]["saved_uploaded_to"] = "已保存上传价格到 {path}"
LANG["en"]["no_signal_history"] = "No signal or realtime pick history found yet. Run daily or realtime mode first."
LANG["zh"]["no_signal_history"] = "尚无信号或实时选股历史。请先运行 daily 或 realtime 模式。"
LANG["en"]["platform_label"] = "Platform"
LANG["zh"]["platform_label"] = "平台"
LANG["en"]["sentiment_score_label"] = "Sentiment Score"
LANG["zh"]["sentiment_score_label"] = "情感分数"
LANG["en"]["monthly_metrics_title"] = "Monthly Metrics"
LANG["zh"]["monthly_metrics_title"] = "月度指标"


def t(key: str) -> str:
    try:
        lang = st.session_state.get("lang", "zh") if hasattr(st, "session_state") else "zh"
    except Exception:
        lang = "zh"
    return LANG.get(lang, LANG["en"]).get(key, key)


def _inject_dashboard_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #F7FAFC 0%, #EEF2FF 100%);
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        .dashboard-hero {
            border: 1px solid rgba(37, 99, 235, 0.14);
            border-radius: 20px;
            padding: 1.2rem 1.4rem;
            background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(239,246,255,0.96));
            box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
            margin-bottom: 1rem;
        }
        .dashboard-kicker {
            font-size: 0.78rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: #2563EB;
            margin-bottom: 0.25rem;
            font-weight: 700;
        }
        .dashboard-title {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.15;
            color: #0F172A;
        }
        .dashboard-subtitle {
            font-size: 0.96rem;
            color: #475569;
            margin-top: 0.35rem;
        }
        .section-surface {
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-radius: 18px;
            background: rgba(255,255,255,0.88);
            padding: 1rem 1.05rem;
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
            margin: 0.8rem 0 1.2rem 0;
        }
        .section-label {
            font-size: 0.88rem;
            font-weight: 700;
            color: #1D4ED8;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.86);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 16px;
            padding: 0.8rem 0.9rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def _latest_file(pattern: str) -> str:
    files = sorted(glob.glob(pattern))
    return files[-1] if files else ""


def _load_latest_realtime_picks(report_dir: str) -> pd.DataFrame:
    path = _latest_file(str(Path(report_dir) / "realtime_picks_*.csv"))
    if not path:
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_latest_alerts(report_dir: str) -> pd.DataFrame:
    path = _latest_file(str(Path(report_dir) / "realtime_alerts_*.jsonl"))
    if not path:
        return pd.DataFrame()
    return pd.read_json(path, lines=True)


def _load_latest_raw_posts(raw_dir: str) -> pd.DataFrame:
    path = _latest_file(str(Path(raw_dir) / "raw_posts_*.csv"))
    if not path:
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_sentiment_history(path: str) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame()
    return pd.read_json(path, lines=True)


def _load_uploaded_price_frame(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()
    try:
        df = pd.read_csv(uploaded_file)
    except Exception:
        return pd.DataFrame()
    try:
        return normalize_price_frame(df)
    except Exception:
        return pd.DataFrame()


def _save_price_frame(df: pd.DataFrame, target_path: str) -> None:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False)


def _load_signal_history(path: str) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame()
    return pd.read_json(path, lines=True)


def _load_latest_monthly_training(report_dir: str) -> tuple[pd.DataFrame, Dict[str, object]]:
    return load_latest_monthly_training(report_dir)


def _platform_contributions(sentiment_df: pd.DataFrame) -> pd.DataFrame:
    if sentiment_df.empty:
        return pd.DataFrame()
    view = sentiment_df.copy()
    view["trade_date"] = pd.to_datetime(view["trade_date"], errors="coerce")
    latest_date = view["trade_date"].max()
    view = view[view["trade_date"] == latest_date]
    if view.empty:
        return pd.DataFrame()
    grouped = (
        view.groupby(["symbol", "platform"], as_index=False)["sentiment_score"]
        .mean()
        .rename(columns={"sentiment_score": "platform_score"})
    )
    grouped["abs_score"] = grouped["platform_score"].abs()
    grouped["weight"] = grouped.groupby("symbol")["abs_score"].transform(
        lambda x: x / x.sum() if x.sum() != 0 else 0.0
    )
    grouped["weight_pct"] = (grouped["weight"] * 100).round(2)
    return grouped.sort_values(["symbol", "weight_pct"], ascending=[True, False])


def _platform_scores_radar(sentiment_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if sentiment_df.empty:
        return pd.DataFrame()
    view = sentiment_df.copy()
    view["trade_date"] = pd.to_datetime(view["trade_date"], errors="coerce")
    latest_date = view["trade_date"].max()
    view = view[(view["trade_date"] == latest_date) & (view["symbol"] == symbol)]
    if view.empty:
        return pd.DataFrame()
    grouped = view.groupby("platform", as_index=False)["sentiment_score"].mean()
    grouped["abs_score"] = grouped["sentiment_score"].abs()
    return grouped


def _score_badge(score: float) -> str:
    if score >= 0.35:
        return "<span style='background:#10B981;color:white;padding:2px 8px;border-radius:10px;'>STRONG</span>"
    if score >= 0.15:
        return "<span style='background:#3B82F6;color:white;padding:2px 8px;border-radius:10px;'>POSITIVE</span>"
    if score <= -0.35:
        return "<span style='background:#EF4444;color:white;padding:2px 8px;border-radius:10px;'>RISK</span>"
    if score <= -0.15:
        return "<span style='background:#F97316;color:white;padding:2px 8px;border-radius:10px;'>WEAK</span>"
    return "<span style='background:#6B7280;color:white;padding:2px 8px;border-radius:10px;'>NEUTRAL</span>"


def _trend_arrow(score: float) -> str:
    if score >= 0.15:
        return "<span style='color:#10B981;font-size:20px;'>▲</span>"
    if score <= -0.15:
        return "<span style='color:#EF4444;font-size:20px;'>▼</span>"
    return "<span style='color:#9CA3AF;font-size:20px;'>■</span>"


def _render_reason_cards(raw_df: pd.DataFrame, picks_df: pd.DataFrame) -> None:
    def _get_text(key: str) -> str:
        try:
            return t(key)
        except Exception:
            lang = st.session_state.get("lang", "zh") if hasattr(st, "session_state") else "zh"
            return LANG.get(lang, LANG["en"]).get(key, key)

    if raw_df.empty or picks_df.empty:
        st.info(_get_text("no_reason_cards"))
        return

    symbols = picks_df["symbol"].dropna().unique().tolist()
    top_symbols = symbols[:3]
    cols = st.columns(len(top_symbols))

    for idx, symbol in enumerate(top_symbols):
        pick_row = picks_df[picks_df["symbol"] == symbol].head(1)
        avg_score = float(pick_row["avg_score"].iloc[0]) if not pick_row.empty else 0.0
        top_rows = _top_comment_rows(raw_df, symbol, top_n=3)
        positive = top_rows["positive"].head(1)
        negative = top_rows["negative"].head(1)
        pos_summary = positive["summary"].iloc[0] if not positive.empty else ""
        neg_summary = negative["summary"].iloc[0] if not negative.empty else ""
        pos_score = float(positive["ai_score"].iloc[0]) if not positive.empty else 0.0
        neg_score = float(negative["ai_score"].iloc[0]) if not negative.empty else 0.0
        risk_hint = _get_text("risk_balanced")
        if pos_score < 0 and neg_score < 0:
            risk_hint = _get_text("risk_high_negative")
        elif abs(pos_score) < 0.05:
            risk_hint = _get_text("risk_weak_signal")

        with cols[idx]:
            st.markdown(f"### {symbol}")
            st.markdown(
                f"<div style='font-size:28px;font-weight:700;'>{_get_text('kpi_label')} {avg_score:.3f} {_trend_arrow(avg_score)}</div>"
                f"<div><b>{_get_text('score_label')}</b>: {avg_score:.3f} {_score_badge(avg_score)}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(f"**{_get_text('positive_highlight')}**: {pos_summary[:160]}")
            st.markdown(f"**{_get_text('negative_highlight')}**: {neg_summary[:160]}")
            st.markdown(
                f"**{_get_text('risk_weak_signal') if risk_hint==_get_text('risk_weak_signal') else _get_text('risk_balanced') if risk_hint==_get_text('risk_balanced') else _get_text('risk_high_negative')}: {risk_hint}\n\n"
                f"**{_get_text('key_fields')}**: platform scores, top comments, alert changes",
            )


def _top_comment_rows(raw_df: pd.DataFrame, symbol: str, top_n: int = 5) -> Dict[str, pd.DataFrame]:
    if raw_df.empty:
        return {"positive": pd.DataFrame(), "negative": pd.DataFrame()}

    view = raw_df[raw_df["symbol"] == symbol].copy()
    view["ai_score"] = pd.to_numeric(view.get("ai_score", 0), errors="coerce").fillna(0.0)
    positive = view.sort_values("ai_score", ascending=False).head(top_n)
    negative = view.sort_values("ai_score", ascending=True).head(top_n)
    return {"positive": positive, "negative": negative}


def main() -> None:
    # language selection
    st.set_page_config(page_title=LANG.get("en", {}).get("page_title", "OpenClaw"), layout="wide")
    _inject_dashboard_styles()
    # default language stored in session_state
    if "lang" not in st.session_state:
        st.session_state["lang"] = "zh"

    # sidebar language selector
    with st.sidebar:
        opts = [("en", LANG.get("en", {}).get("language_en", "English")), ("zh", LANG.get("zh", {}).get("language_zh", "中文"))]
        cur = st.session_state.get("lang", "zh")
        idx = 0 if cur == "en" else 1
        sel = st.selectbox(t("language_label"), options=opts, index=idx, key="_lang_display", format_func=lambda x: x[1])
        if isinstance(sel, tuple):
            st.session_state["lang"] = sel[0]

    st.markdown(
        f"""
        <div class="dashboard-hero">
            <div class="dashboard-kicker">OpenClaw AI</div>
            <div class="dashboard-title">{t('header_title')}</div>
            <div class="dashboard-subtitle">{t('evaluation')} · {t('monthly_training')} · {t('platform_radar')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    report_dir = st.sidebar.text_input(t("report_dir"), "data/reports")
    raw_dir = st.sidebar.text_input(t("raw_dir"), "data/raw")
    memory_dir = st.sidebar.text_input(t("memory_dir"), "data/memory")

    with st.sidebar.expander(t("quick_start"), expanded=True):
        st.markdown(t("tutorial_markdown"))

    # Realtime picks
    st.subheader(t("realtime_picks"))
    picks_df = _load_latest_realtime_picks(report_dir)
    if picks_df.empty:
        st.info(t("no_realtime_picks"))
    else:
        st.dataframe(picks_df, use_container_width=True)

    # Alerts
    st.subheader(t("score_alerts"))
    alerts_df = _load_latest_alerts(report_dir)
    if alerts_df.empty:
        st.info(t("no_alerts"))
    else:
        st.dataframe(alerts_df, use_container_width=True)

    # Sentiment trend
    st.subheader(t("sentiment_trend"))
    sentiment_df = _load_sentiment_history(str(Path(memory_dir) / "sentiment_history.jsonl"))
    with st.container(border=True):
        if not sentiment_df.empty:
            sentiment_df["trade_date"] = pd.to_datetime(sentiment_df["trade_date"], errors="coerce")
            chart = (
                alt.Chart(sentiment_df)
                .mark_line(point=True, strokeWidth=2.4)
                .encode(
                    x=alt.X("trade_date:T", title=t("month")),
                    y=alt.Y("sentiment_score:Q", title=t("sentiment_score_label")),
                    color=alt.Color("platform:N", scale=alt.Scale(scheme="category10"), title=t("platform_label")),
                    tooltip=["trade_date", "platform", "symbol", "sentiment_score"],
                )
                .properties(title=t("sentiment_trend"), height=280)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info(t("no_sentiment_history"))

    # Platform contribution
    st.subheader(t("platform_contribution"))
    contrib_df = _platform_contributions(sentiment_df)
    with st.container(border=True):
        if contrib_df.empty:
            st.info(t("no_contribution_data"))
        else:
            symbol = st.selectbox(t("select_symbol_for_contribution"), sorted(contrib_df["symbol"].unique()))
            view = contrib_df[contrib_df["symbol"] == symbol]
            display_df = view[["platform", "platform_score", "weight_pct"]].rename(
                columns={
                    "platform": t("col_platform"),
                    "platform_score": t("col_platform_score"),
                    "weight_pct": t("col_weight_pct"),
                }
            )
            st.dataframe(display_df, use_container_width=True)

            bar = (
                alt.Chart(view)
                .mark_bar(cornerRadiusEnd=6)
                .encode(
                    x=alt.X("weight_pct:Q", title=t("contribution_pct")),
                    y=alt.Y("platform:N", sort="-x", title=None),
                    color=alt.Color("platform:N", scale=alt.Scale(scheme="tableau10"), title=t("platform_label")),
                    tooltip=["platform", "weight_pct", "platform_score"],
                )
                .properties(title=t("platform_contribution"), height=240)
            )
            st.altair_chart(bar, use_container_width=True)

            donut = (
                alt.Chart(view)
                .mark_arc(innerRadius=68, outerRadius=120)
                .encode(
                    theta=alt.Theta("weight_pct:Q"),
                    color=alt.Color("platform:N", scale=alt.Scale(scheme="tableau10"), title=t("platform_label")),
                    tooltip=["platform", "weight_pct", "platform_score"],
                )
                .properties(title=t("platform_contribution"), height=280)
            )
            st.altair_chart(donut, use_container_width=True)

    # Radar
    st.subheader(t("platform_radar"))
    radar_symbol = st.selectbox(t("select_symbol_for_radar"), sorted(sentiment_df["symbol"].unique()) if not sentiment_df.empty else [])
    radar_df = _platform_scores_radar(sentiment_df, radar_symbol) if radar_symbol else pd.DataFrame()
    with st.container(border=True):
        if radar_df.empty:
            st.info(t("no_radar_data"))
        else:
            max_val = float(radar_df["abs_score"].max() or 1)
            radar_area = (
                alt.Chart(radar_df)
                .mark_area(opacity=0.18)
                .encode(
                    theta=alt.Theta("platform:N", title=None),
                    radius=alt.Radius("abs_score:Q", scale=alt.Scale(domain=[0, max_val])),
                    color=alt.Color("platform:N", scale=alt.Scale(scheme="tableau10"), title=t("platform_label")),
                    tooltip=["platform", "sentiment_score"],
                )
            )
            radar_shadow = (
                alt.Chart(radar_df)
                .mark_line(point=True, strokeWidth=5, opacity=0.14)
                .encode(
                    theta=alt.Theta("platform:N", title=None),
                    radius=alt.Radius("abs_score:Q", scale=alt.Scale(domain=[0, max_val])),
                    color=alt.value("#2563EB"),
                )
            )
            radar_line = (
                alt.Chart(radar_df)
                .mark_line(point=alt.OverlayMarkDef(filled=True, size=85), strokeWidth=2.6)
                .encode(
                    theta=alt.Theta("platform:N", title=None),
                    radius=alt.Radius("abs_score:Q", scale=alt.Scale(domain=[0, max_val])),
                    color=alt.value("#0F172A"),
                    tooltip=["platform", "sentiment_score"],
                )
            )
            radar = (radar_area + radar_shadow + radar_line).properties(title=t("platform_radar"), height=360)
            st.altair_chart(radar, use_container_width=True)

    # Top comments
    st.subheader(t("top_comments"))
    raw_df = _load_latest_raw_posts(raw_dir)
    if raw_df.empty:
        st.info(t("no_raw_posts"))
    else:
        sel_symbol = st.selectbox(t("select_symbol"), sorted(raw_df["symbol"].unique()))
        top_rows = _top_comment_rows(raw_df, sel_symbol)
        st.markdown(f"**{t('positive_highlight')}**")
        pos_df = top_rows["positive"][['title', 'summary', 'ai_score', 'url']].rename(
            columns={
                'title': t('col_title'),
                'summary': t('col_summary'),
                'ai_score': t('col_ai_score'),
                'url': t('col_url'),
            }
        )
        st.dataframe(pos_df, use_container_width=True)
        st.markdown(f"**{t('negative_highlight')}**")
        neg_df = top_rows["negative"][['title', 'summary', 'ai_score', 'url']].rename(
            columns={
                'title': t('col_title'),
                'summary': t('col_summary'),
                'ai_score': t('col_ai_score'),
                'url': t('col_url'),
            }
        )
        st.dataframe(neg_df, use_container_width=True)

    # Pick reason cards
    st.subheader(t("pick_reason_cards"))
    if raw_df.empty or picks_df.empty:
        st.info(t("run_realtime_daily_first"))
    else:
        _render_reason_cards(raw_df, picks_df)

    # Evaluation
    st.subheader(t("evaluation"))
    price_source_mode = st.radio(
        t("price_source"),
        LANG.get(st.session_state.get("lang", "zh"), LANG["en"]).get("price_options", []),
        horizontal=True,
        index=0,
    )
    uploaded_price_file = st.file_uploader(t("upload_label"), type=["csv"], key="price_upload")
    price_csv = st.text_input(t("local_csv_path"), "data/reports/price_history_cache.csv")
    if uploaded_price_file is not None:
        uploaded_price_df = _load_uploaded_price_frame(uploaded_price_file)
        if uploaded_price_df.empty:
            st.warning(t("uploaded_invalid"))
        else:
            st.caption(
                f"{t('uploaded_rows')}: {len(uploaded_price_df)} | {t('symbols_count')}: {uploaded_price_df['symbol'].nunique()}"
            )
            if st.button(t("save_uploaded")):
                _save_price_frame(uploaded_price_df, price_csv)
                st.success(t("saved_uploaded_to").format(path=price_csv))

    start_date = st.text_input(t("start_date"), "")
    end_date = st.text_input(t("end_date"), "")

    if st.button(t("run_evaluation")):
        try:
            signals_path = str(Path(memory_dir) / "signal_history.jsonl")
            signal_df = pd.read_json(signals_path, lines=True) if Path(signals_path).exists() else pd.DataFrame()
            if not signal_df.empty:
                signal_df["trade_date"] = pd.to_datetime(signal_df["trade_date"], errors="coerce")
            if price_source_mode == "Upload CSV":
                price_df = _load_uploaded_price_frame(uploaded_price_file)
                if price_df.empty:
                    st.warning(t("upload_required"))
                    return
            elif price_source_mode == "Local CSV path":
                price_df = load_prices(price_csv)
            else:
                if not start_date or not end_date:
                    st.warning(t("yahoo_need_dates"))
                    return
                symbols = sorted(signal_df["symbol"].dropna().unique()) if not signal_df.empty else []
                price_df = fetch_prices_with_timeout(symbols, start_date, end_date)
                if price_df.empty:
                    st.warning(t("yahoo_no_prices"))
                    return
            merged, summary = evaluate_signals(signal_df, price_df, start_date or None, end_date or None)
            st.markdown(
                f"**{t('eval_accuracy')}**: {summary.accuracy:.2%} | **{t('eval_avg_return')}**: {summary.avg_return:.4%} | "
                f"**{t('eval_win_rate')}**: {summary.win_rate:.2%} | **{t('eval_sharpe_like')}**: {summary.sharpe_like:.4f}"
            )
            if not merged.empty:
                st.dataframe(merged[["trade_date", "symbol", "action", "next_return", "correct"]], use_container_width=True)
        except Exception as e:
            st.error(t("evaluation_failed").format(error=e))

    # Monthly training / forecast
    st.subheader(t("monthly_training"))
    train_months = st.slider(t("training_lookback"), min_value=1, max_value=24, value=6)
    run_monthly_train = st.button(t("refresh_monthly"))

    signal_history_df = load_training_history(memory_dir)
    monthly_df, monthly_summary = _load_latest_monthly_training(report_dir)

    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric(t("realtime_picks"), len(picks_df))
    with summary_cols[1]:
        st.metric(t("score_alerts"), len(alerts_df))
    with summary_cols[2]:
        st.metric(t("sentiment_trend"), 0 if sentiment_df.empty else sentiment_df["platform"].nunique())
    with summary_cols[3]:
        st.metric(t("monthly_training"), 0 if monthly_df.empty else len(monthly_df))

    if run_monthly_train:
        if signal_history_df.empty:
            st.info(t("no_signal_history"))
        else:
            signal_history_df["trade_date"] = pd.to_datetime(signal_history_df["trade_date"], errors="coerce")
            signal_history_df = signal_history_df.dropna(subset=["trade_date", "symbol"])
            if signal_history_df.empty:
                st.info(t("valid_dates_missing"))
            else:
                max_trade_date = signal_history_df["trade_date"].max()
                min_trade_date = (max_trade_date - pd.DateOffset(months=max(1, train_months) - 1)).normalize()
                symbols = sorted(signal_history_df["symbol"].dropna().unique())
                try:
                    if price_source_mode == "Upload CSV":
                        train_price_df = _load_uploaded_price_frame(uploaded_price_file)
                        if train_price_df.empty:
                            raise ValueError("upload CSV is empty or invalid")
                    elif price_source_mode == "Local CSV path":
                        train_price_df = load_prices(price_csv)
                    else:
                        train_price_df = fetch_prices_with_timeout(
                            symbols,
                            min_trade_date.strftime("%Y-%m-%d"),
                            max_trade_date.strftime("%Y-%m-%d"),
                        )
                        if train_price_df.empty:
                            raise ValueError(t("empty_yahoo_prices"))
                    monthly_df, monthly_summary_obj = build_monthly_training_frame(
                        signal_history_df,
                        train_price_df,
                        months=train_months,
                    )
                    outputs = save_monthly_training_report(report_dir, monthly_df, monthly_summary_obj)
                    monthly_df, monthly_summary = _load_latest_monthly_training(report_dir)
                    st.success(f"{t('monthly_saved')}: {outputs['csv']}")
                except Exception as e:
                    st.error(t("monthly_failed").format(error=e))

    with st.container(border=True):
        if monthly_df.empty:
            st.info(t("no_monthly_report"))
        else:
            summary_data = monthly_summary.get("summary", {}) if isinstance(monthly_summary, dict) else {}
        if summary_data:
            cols = st.columns(4)
            with cols[0]:
                st.metric(t("metric_forecast_success_rate"), f"{float(summary_data.get('forecast_success_rate', 0.0)):.2%}")
            with cols[1]:
                st.metric(t("metric_rolling_success_rate"), f"{float(summary_data.get('rolling_success_rate', 0.0)):.2%}")
            with cols[2]:
                st.metric(t("metric_latest_month_accuracy"), f"{float(summary_data.get('latest_month_accuracy', 0.0)):.2%}")
            with cols[3]:
                st.metric(t("metric_forecast_direction"), str(summary_data.get('forecast_direction', 'NEUTRAL')))

            if summary_data.get("start_month") and summary_data.get("end_month"):
                st.caption(
                    f"{t('coverage')}: {summary_data.get('start_month')} -> {summary_data.get('end_month')} | "
                    f"{t('signal_count')}: {summary_data.get('total_signals', 0)}"
                )

        monthly_df = monthly_df.copy()
        if not monthly_df.empty:
            monthly_df["accuracy"] = pd.to_numeric(monthly_df.get("accuracy", 0), errors="coerce").fillna(0.0)
            monthly_df["avg_return"] = pd.to_numeric(monthly_df.get("avg_return", 0), errors="coerce").fillna(0.0)
            monthly_df["signals"] = pd.to_numeric(monthly_df.get("signals", 0), errors="coerce").fillna(0.0)
            monthly_df["win_rate"] = pd.to_numeric(monthly_df.get("win_rate", 0), errors="coerce").fillna(0.0)

            monthly_line = (
                alt.Chart(monthly_df)
                .transform_fold(["accuracy", "win_rate"], as_=["metric", "value"])
                .mark_line(point=True)
                .encode(
                    x=alt.X("month:N", title=t("month")),
                    y=alt.Y("value:Q", title=t("rate")),
                    color=alt.Color("metric:N", scale=alt.Scale(scheme="tableau10"), title=t("metric_forecast_direction")),
                    tooltip=["month", "metric", "value"],
                )
                .properties(title=t("monthly_metrics_title"), height=260)
            )
            st.altair_chart(monthly_line, use_container_width=True)

            monthly_bar = (
                alt.Chart(monthly_df)
                .mark_bar()
                .encode(
                    x=alt.X("month:N", title=t("month")),
                    y=alt.Y("signals:Q", title=t("signal_count")),
                    color=alt.Color("accuracy:Q", scale=alt.Scale(scheme="tealblues"), title=t("eval_accuracy")),
                    tooltip=["month", "signals", "accuracy", "avg_return", "win_rate"],
                )
                .properties(title=t("monthly_metrics_title"), height=250)
            )
            st.altair_chart(monthly_bar, use_container_width=True)

            monthly_display = monthly_df[["month", "signals", "correct_signals", "accuracy", "avg_return", "win_rate", "avg_confidence"]].rename(
                columns={
                    "month": t("month"),
                    "signals": t("signal_count"),
                    "correct_signals": "correct_signals",
                    "accuracy": t("metric_latest_month_accuracy"),
                    "avg_return": t("eval_avg_return"),
                    "win_rate": t("eval_win_rate"),
                    "avg_confidence": "avg_confidence",
                }
            )
            st.dataframe(
                monthly_display,
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
