from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Dict

import altair as alt
import pandas as pd
import streamlit as st

from opinion_trading.core.evaluation import (
    evaluate_signals,
    load_prices,
    normalize_price_frame,
)
from opinion_trading.core.monthly_training import (
    build_monthly_training_frame,
    fetch_prices_with_timeout,
    load_latest_monthly_training,
    load_training_history,
    save_monthly_training_report,
)

from opinion_trading.core.openclaw_adapter import OpenClawClient
from opinion_trading.ui_helpers import (
    build_openclaw_activity_feed,
    build_openclaw_summary,
    build_pick_contribution,
    build_pick_narrative,
    build_picks_detail_table,
    evidence_stats,
    filter_usable_raw,
    infer_score_source,
    label_platform_column,
    monthly_methodology_text,
    parse_platform_scores,
    platform_label,
    symbol_display,
    top_comment_rows,
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
        "click_to_expand": "Click to view full comment",
        "col_post_time": "Time",
        "key_fields": "Key fields",
        "key_fields_help": "Each row shows one platform sentiment score for a ranked stock. **Avg sentiment** is the weighted composite (-1 bearish ~ +1 bullish).",
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
        "non_zero_rate_pct": "Non-zero Rate %",
        "lookback_days_non_zero": "Lookback days for non-zero rate",
        "col_non_zero_rate": "non_zero_rate_pct",
        "col_observations": "observations",
        "col_title": "title",
        "col_summary": "summary",
        "col_ai_score": "ai_score",
        "col_url": "url",
        "tab_picks": "Picks",
        "tab_sentiment": "Sentiment",
        "tab_comments": "Evidence",
        "tab_eval": "Backtest",
        "status_last_report": "Latest report",
        "status_running_hint": "Realtime job may still be running — refresh to update.",
        "rank_label": "Rank",
        "refresh_data": "Refresh data",
        "sidebar_paths": "Data paths",
        "hero_tagline": "OpenClaw monitors sentiment in real time · DeepSeek scoring · AI stock picks",
        "user_guide_title": "What you can do here",
        "user_guide_body": """
1. **Realtime Picks** — OpenClaw aggregates multi-platform sentiment into Top 3 rankings and reason cards.  
2. **OpenClaw Live** — See the AI pipeline, analysis feed, and which texts were scored by OpenClaw vs keyword fallback.  
3. **Sentiment** — Platform trends and contribution weights.  
4. **Evidence** — User comments + reference texts that support each pick.  

Connect OpenClaw via `OPENCLAW_URL` (see `scripts/run_demo_openclaw.ps1`). Sidebar shows live connection status.
""",
        "tab_openclaw": "OpenClaw Live",
        "openclaw_status_title": "OpenClaw Engine",
        "openclaw_connected": "Connected",
        "openclaw_disconnected": "Not connected (keyword fallback)",
        "openclaw_url_label": "Endpoint",
        "openclaw_probe_btn": "Test connection",
        "openclaw_rescore_btn": "Re-score visible comments with OpenClaw",
        "openclaw_rescore_hint": "Requires OPENCLAW_URL. Scores update in this session only.",
        "openclaw_rescore_done": "OpenClaw re-scored {n} comments.",
        "openclaw_pipeline_title": "OpenClaw realtime pipeline",
        "openclaw_pipeline_body": """
**Step 1 · Collect** — Crawl Guba, Xueqiu, Weibo, etc. for target symbols.  
**Step 2 · OpenClaw score** — Batch sentiment via OpenClaw Gateway → DeepSeek (`/api/v1/sentiment`).  
**Step 3 · Aggregate** — Platform-weighted composite score per symbol.  
**Step 4 · Recommend** — Rank Top N picks and generate explainable reason cards.
""",
        "openclaw_summary_title": "This run at a glance",
        "openclaw_summary_fmt": "Raw {total_raw} · Usable {usable} · User comments {user_comments} · OpenClaw-scored {openclaw_scored} · Keyword {keyword_scored} · Picks {pick_count}",
        "openclaw_activity_title": "Latest analysis feed",
        "openclaw_pick_rec_title": "OpenClaw recommendations",
        "openclaw_pick_rec_body": "Composite scores from the latest realtime run. Platform layer uses OpenClaw when connected; row-level batch scoring runs when `OPENCLAW_SKIP_ROW_SCORE=0`.",
        "openclaw_not_connected_hint": "OpenClaw is offline — showing keyword scores. Run `scripts/run_demo_openclaw.ps1` to enable AI scoring.",
        "reference_comments": "Reference texts (news / analysis)",
        "badge_openclaw": "OpenClaw AI",
        "badge_keyword": "Keyword",
        "badge_user_comment": "User opinion",
        "badge_news": "News",
        "badge_reference": "Reference",
        "no_platform_scores": "No platform breakdown",
        "guide_trend_title": "How to read: Sentiment trend",
        "guide_trend_body": "Each line is one platform's monthly average sentiment (-1 bearish ~ +1 bullish). Rising lines = improving mood. Use **Min samples** to hide thin data.",
        "guide_contrib_title": "How to read: Platform contribution",
        "guide_contrib_body": "Scores come from the latest realtime pick; weights from config/settings.yaml. **Weighted contrib** = score × platform weight. Higher **weight %** = stronger driver for this pick.",
        "guide_snapshot_title": "Platform sentiment snapshot",
        "guide_snapshot_body": "Latest score per platform for the selected symbol. Green = bullish, red = bearish, gray = neutral/no signal.",
        "guide_comments_title": "How to read: Evidence comments",
        "guide_comments_body": "User opinions are ranked by OpenClaw/keyword sentiment. Reference texts (news, analysis) are shown separately with lower weight. **Click to expand** full text and source link.",
        "sample_low_warning": "Low sample count — platform stats may be unreliable. Run daily/realtime to collect more posts.",
        "evidence_summary": "Evidence: {valid} user comments / {total} raw rows, {platforms} platforms, {fallback} noise filtered, {news_filtered} news filtered",
        "comments_few_hint": "Few user comments remain after filtering news. Re-run daily mode to collect more Guba/Xueqiu discussions.",
        "no_valid_comments": "No valid comments after filtering fallback/noise. Re-run daily mode for fresher data.",
        "pick_story": "Pick narrative",
        "platform_snapshot": "Platform snapshot",
        "col_config_weight": "config weight",
        "col_weighted_contrib": "weighted contrib",
        "col_direction": "direction",
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
        "click_to_expand": "点击展开查看完整评论",
        "col_post_time": "时间",
        "key_fields": "选股明细",
        "key_fields_help": "下表按「排名 → 股票 → 各平台情感分」展开。**综合情感分**为加权汇总（-1 偏空 ~ +1 偏多），**平台情感分**为各渠道 AI 打分。",
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
        "non_zero_rate_pct": "非零率 %",
        "lookback_days_non_zero": "非零率回看天数",
        "col_non_zero_rate": "非零率 %",
        "col_observations": "样本数",
        "col_title": "标题",
        "col_summary": "摘要",
        "col_ai_score": "AI 分数",
        "col_url": "链接",
        "tab_picks": "实时选股",
        "tab_sentiment": "舆情分析",
        "tab_comments": "评论依据",
        "tab_eval": "回测评估",
        "status_last_report": "最新报告",
        "status_running_hint": "选股任务可能仍在运行，点击刷新查看最新结果。",
        "rank_label": "排名",
        "refresh_data": "刷新数据",
        "sidebar_paths": "数据路径",
        "hero_tagline": "OpenClaw 实时监测舆情 · DeepSeek 情感分析 · AI 智能选股",
        "user_guide_title": "你可以这样使用本页",
        "user_guide_body": """
1. **实时选股** — OpenClaw 汇总多平台情感分，输出 Top 3 排名与选股原因卡。  
2. **OpenClaw 实时** — 查看 AI 分析流水线、逐条分析流水，以及 OpenClaw / 关键词 打分来源。  
3. **舆情分析** — 各平台趋势与贡献权重。  
4. **评论依据** — 用户观点 + 参考文本，支撑选股结论。  

连接 OpenClaw：设置 `OPENCLAW_URL` 或运行 `scripts/run_demo_openclaw.ps1`；侧边栏显示连接状态。
""",
        "tab_openclaw": "OpenClaw 实时",
        "openclaw_status_title": "OpenClaw 分析引擎",
        "openclaw_connected": "已连接",
        "openclaw_disconnected": "未连接（当前为关键词兜底）",
        "openclaw_url_label": "服务地址",
        "openclaw_probe_btn": "测试连接",
        "openclaw_rescore_btn": "用 OpenClaw 重新分析当前评论",
        "openclaw_rescore_hint": "需配置 OPENCLAW_URL；分数仅在本会话内更新。",
        "openclaw_rescore_done": "OpenClaw 已重新分析 {n} 条评论。",
        "openclaw_pipeline_title": "OpenClaw 实时分析流水线",
        "openclaw_pipeline_body": """
**① 采集** — 从股吧、雪球、微博等平台抓取目标股票相关文本。  
**② OpenClaw 打分** — 经 OpenClaw Gateway 调用 DeepSeek，批量输出情感分（`/api/v1/sentiment`）。  
**③ 加权聚合** — 按平台权重汇总为综合舆情分。  
**④ 选股推荐** — 排名 Top N 并生成可解释的推荐原因卡。
""",
        "openclaw_summary_title": "本轮分析概览",
        "openclaw_summary_fmt": "原始 {total_raw} 条 · 可用 {usable} 条 · 用户观点 {user_comments} 条 · OpenClaw 打分 {openclaw_scored} 条 · 关键词 {keyword_scored} 条 · 推荐 {pick_count} 只",
        "openclaw_activity_title": "最新分析流水",
        "openclaw_pick_rec_title": "OpenClaw 选股推荐",
        "openclaw_pick_rec_body": "综合分来自最近一次 realtime 运行。平台层在 OpenClaw 在线时使用 AI 打分；逐帖批量打分需设置 `OPENCLAW_SKIP_ROW_SCORE=0`。",
        "openclaw_not_connected_hint": "OpenClaw 未连接，当前展示关键词分数。运行 `scripts/run_demo_openclaw.ps1` 可启用 AI 分析。",
        "reference_comments": "参考文本（新闻 / 分析，权重较低）",
        "badge_openclaw": "OpenClaw AI",
        "badge_keyword": "关键词",
        "badge_user_comment": "用户观点",
        "badge_news": "新闻",
        "badge_reference": "参考",
        "no_platform_scores": "暂无平台分数明细",
        "guide_trend_title": "图表说明：情感趋势",
        "guide_trend_body": "每条折线代表一个平台的**月度平均情感分**（-1 偏空 ~ +1 偏多）。上行=情绪改善，下行=情绪恶化。可通过「Min samples」过滤样本过少的平台。",
        "guide_contrib_title": "图表说明：平台贡献（选股解释）",
        "guide_contrib_body": "分数来自**最新一轮 realtime 选股**的各平台分项；权重来自 config/settings.yaml。**加权贡献 = 分数 × 平台权重**，**贡献 %** 越高表示该平台对本次排名影响越大。",
        "guide_snapshot_title": "平台情感快照",
        "guide_snapshot_body": "展示所选股票在各平台的**最新情感分**。绿色偏多、红色偏空、灰色中性/无信号，便于快速对比强弱平台。",
        "guide_comments_title": "图表说明：评论依据",
        "guide_comments_body": "用户观点按 OpenClaw/关键词 情感分排序；新闻与分析类参考文本单独展示（权重较低）。**点击评论可展开**查看完整正文与原文链接。",
        "sample_low_warning": "⚠️ 当前样本偏少，平台统计可能不准确。建议多跑几次 daily/realtime 积累数据。",
        "evidence_summary": "证据统计：用户评论 {valid}/{total} 条，覆盖 {platforms} 个平台，已过滤噪声 {fallback} 条、新闻 {news_filtered} 条",
        "comments_few_hint": "过滤新闻后用户评论较少，建议重新运行 daily 模式，优先采集股吧/雪球讨论帖。",
        "no_valid_comments": "过滤噪声后暂无有效评论。请重新运行 daily 模式抓取最新帖子。",
        "pick_story": "选股叙事",
        "platform_snapshot": "平台情感快照",
        "col_config_weight": "配置权重",
        "col_weighted_contrib": "加权贡献",
        "col_direction": "方向",
    },
}

# additional translation keys
LANG["en"]["saved_uploaded_to"] = "Saved uploaded prices to {path}"
LANG["zh"]["saved_uploaded_to"] = "已保存上传价格到 {path}"
LANG["en"][
    "no_signal_history"
] = "No signal or realtime pick history found yet. Run daily or realtime mode first."
LANG["zh"]["no_signal_history"] = "尚无信号或实时选股历史。请先运行 daily 或 realtime 模式。"
LANG["en"]["platform_label"] = "Platform"
LANG["zh"]["platform_label"] = "平台"
LANG["en"]["sentiment_score_label"] = "Sentiment Score"
LANG["zh"]["sentiment_score_label"] = "情感分数"
LANG["en"]["monthly_metrics_title"] = "Monthly Metrics"
LANG["zh"]["monthly_metrics_title"] = "月度指标"


def t(key: str) -> str:
    try:
        lang = (
            st.session_state.get("lang", "zh") if hasattr(st, "session_state") else "zh"
        )
    except Exception:
        lang = "zh"
    return LANG.get(lang, LANG["en"]).get(key, key)


def _ui_lang() -> str:
    try:
        return str(st.session_state.get("lang", "zh"))
    except Exception:
        return "zh"


def _platform_label(name: str) -> str:
    return platform_label(name, _ui_lang())


def _symbol_label(symbol: str) -> str:
    return symbol_display(symbol, _ui_lang())


def _evidence_caption(stats: dict) -> str:
    return t("evidence_summary").format(
        valid=stats["valid"],
        total=stats["total"],
        platforms=stats["platforms"],
        fallback=stats["fallback"],
        news_filtered=stats.get("news_filtered", 0),
    )


def _openclaw_client() -> OpenClawClient:
    if "_openclaw_client" not in st.session_state:
        st.session_state["_openclaw_client"] = OpenClawClient()
    return st.session_state["_openclaw_client"]


def _openclaw_probe(force: bool = False) -> Dict[str, object]:
    client = _openclaw_client()
    if not client.is_configured():
        return {
            "connected": False,
            "url": None,
            "message": "OPENCLAW_URL not set",
        }
    if not force and "_openclaw_probe" in st.session_state:
        return st.session_state["_openclaw_probe"]
    result = client.probe()
    st.session_state["_openclaw_probe"] = result
    return result


def _bootstrap_openclaw_env() -> None:
    """Load project .env and default local OpenClaw URL for Streamlit sessions."""
    root = Path(__file__).resolve().parents[2]
    env_path = root / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            piece = line.strip()
            if not piece or piece.startswith("#") or "=" not in piece:
                continue
            key, _, val = piece.partition("=")
            os.environ.setdefault(key.strip(), val.strip())
    os.environ.setdefault("OPENCLAW_URL", "http://127.0.0.1:18790")
    os.environ.setdefault("OPENCLAW_TIMEOUT", "120")
    os.environ.setdefault("OPENCLAW_PROBE_TIMEOUT", "120")


def _render_openclaw_sidebar() -> None:
    st.markdown(f"#### {t('openclaw_status_title')}")
    probe = _openclaw_probe()
    connected = bool(probe.get("connected"))
    status_text = t("openclaw_connected") if connected else t("openclaw_disconnected")
    css = "openclaw-on" if connected else "openclaw-off"
    st.markdown(
        f"<span class='status-pill {css}'>OpenClaw · {status_text}</span>",
        unsafe_allow_html=True,
    )
    if probe.get("url"):
        st.caption(f"{t('openclaw_url_label')}: `{probe['url']}`")
    if probe.get("message") and not connected:
        st.caption(str(probe.get("message", ""))[:120])
    if st.button(t("openclaw_probe_btn"), use_container_width=True, key="oc_probe_btn"):
        st.session_state.pop("_openclaw_probe", None)
        _openclaw_probe(force=True)
        st.rerun()
    if not connected:
        st.info(t("openclaw_not_connected_hint"))


def _render_openclaw_pipeline_banner() -> None:
    steps = [
        "① 采集" if _ui_lang() == "zh" else "1. Collect",
        "② OpenClaw" if _ui_lang() == "zh" else "2. OpenClaw",
        "③ 聚合" if _ui_lang() == "zh" else "3. Aggregate",
        "④ 推荐" if _ui_lang() == "zh" else "4. Recommend",
    ]
    st.markdown(
        "<div class='pipeline-flow'>"
        + "".join(f"<div class='pipeline-step'>{s}</div>" for s in steps)
        + "</div>",
        unsafe_allow_html=True,
    )


def _comment_badges_html(row: pd.Series) -> str:
    source = str(row.get("score_source") or infer_score_source(row))
    ctype = str(row.get("content_type") or "reference")
    engine_cls = "ai" if source == "openclaw" else "kw"
    engine_label = t("badge_openclaw") if source == "openclaw" else t("badge_keyword")
    type_map = {
        "user_comment": ("user", t("badge_user_comment")),
        "news": ("news", t("badge_news")),
        "reference": ("ref", t("badge_reference")),
    }
    type_cls, type_label = type_map.get(ctype, ("ref", t("badge_reference")))
    return (
        f"<span class='oc-badge {engine_cls}'>{engine_label}</span>"
        f"<span class='oc-badge {type_cls}'>{type_label}</span>"
    )


def _apply_openclaw_rescore(comments_df: pd.DataFrame) -> pd.DataFrame:
    if comments_df.empty:
        return comments_df
    client = _openclaw_client()
    if not client.is_configured():
        return comments_df
    texts = [
        str(r.get("full_text") or r.get("display_text") or "")
        for _, r in comments_df.iterrows()
    ]
    texts = [t for t in texts if t.strip()]
    if not texts:
        return comments_df
    scores = client.score_texts(texts)
    if not scores or len(scores) != len(texts):
        return comments_df
    out = comments_df.copy()
    for idx, score in zip(out.index, scores):
        out.at[idx, "ai_score"] = float(score)
        out.at[idx, "score_source"] = "openclaw"
    return out


def _render_openclaw_tab(
    raw_df: pd.DataFrame, picks_df: pd.DataFrame, report_dir: str
) -> None:
    probe = _openclaw_probe()
    _render_info_box(t("openclaw_pipeline_title"), t("openclaw_pipeline_body"))
    _render_openclaw_pipeline_banner()

    summary = build_openclaw_summary(raw_df, picks_df)
    st.markdown(f"#### {t('openclaw_summary_title')}")
    st.markdown(
        t("openclaw_summary_fmt").format(**summary),
        unsafe_allow_html=True,
    )
    if not probe.get("connected"):
        st.warning(t("openclaw_not_connected_hint"))

    st.markdown(f"#### {t('openclaw_pick_rec_title')}")
    st.caption(t("openclaw_pick_rec_body"))
    if picks_df.empty:
        st.info(t("no_realtime_picks"))
    else:
        rec = build_picks_detail_table(picks_df, _ui_lang())
        st.dataframe(rec, use_container_width=True, hide_index=True)

    st.markdown(f"#### {t('openclaw_activity_title')}")
    feed = build_openclaw_activity_feed(raw_df, limit=30, lang=_ui_lang())
    if feed.empty:
        st.info(t("no_raw_posts"))
    else:
        st.dataframe(feed, use_container_width=True, hide_index=True)

    if not raw_df.empty:
        st.caption(t("openclaw_rescore_hint"))
        symbols = sorted(raw_df["symbol"].dropna().unique().tolist())
        sym = st.selectbox(t("select_symbol"), symbols, key="oc_rescore_symbol")
        if st.button(t("openclaw_rescore_btn"), key="oc_rescore_btn"):
            rows = top_comment_rows(raw_df, sym, top_n=15, include_reference=True)
            merged = pd.concat(
                [rows["positive"], rows["negative"], rows["reference"]],
                ignore_index=True,
            ).drop_duplicates(subset=["url"], keep="first")
            rescored = _apply_openclaw_rescore(merged)
            st.session_state[f"_oc_rescored_{sym}"] = rescored
            st.success(t("openclaw_rescore_done").format(n=len(rescored)))
        cached = st.session_state.get(f"_oc_rescored_{sym}")
        if isinstance(cached, pd.DataFrame) and not cached.empty:
            st.markdown(f"**OpenClaw re-score · {_symbol_label(sym)}**")
            _render_comment_highlights(cached, key_prefix=f"oc_live_{sym}")


# Dashboard design tokens (Impeccable product-UI register)
_DASH_ACCENT = "#0D9488"
_DASH_COLORS = [
    "#0D9488",
    "#047857",
    "#115E59",
    "#134E4A",
    "#B45309",
    "#5C6B63",
    "#0F766E",
    "#6B7280",
]
_SENTIMENT_BAR_SCALE = alt.Scale(
    domain=["bull", "bear", "flat"],
    range=["#047857", "#B91C1C", "#5C6B63"],
)


def _sentiment_color(score: float) -> str:
    if score > 0.05:
        return "#047857"
    if score < -0.05:
        return "#B91C1C"
    return "#5C6B63"


def _platform_chip_html(platform: str, score: float, *, suffix: str = "") -> str:
    label = _platform_label(platform)
    text = f"{label} {score:+.3f}{suffix}" if suffix else f"{label} {score:+.3f}"
    color = _sentiment_color(score)
    return (
        f"<span class='platform-chip' style='color:{color};'>"
        f"<span class='platform-chip-label'>{text}</span></span>"
    )


def _configure_chart(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure_axis(
            labelFont="IBM Plex Sans",
            titleFont="IBM Plex Sans",
            labelColor="#4A5750",
            titleColor="#121820",
            gridColor="rgba(120, 132, 124, 0.22)",
            domainColor="rgba(120, 132, 124, 0.35)",
        )
        .configure_view(strokeWidth=0)
        .configure_title(
            font="IBM Plex Sans",
            fontSize=14,
            fontWeight=600,
            color="#121820",
        )
        .configure_legend(
            labelFont="IBM Plex Sans",
            titleFont="IBM Plex Sans",
            labelColor="#4A5750",
            titleColor="#121820",
        )
    )


def _inject_dashboard_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --dash-bg: #F3F5F4;
            --dash-surface: #FAFBFA;
            --dash-ink: #121820;
            --dash-muted: #4A5750;
            --dash-subtle: #5C6B63;
            --dash-border: rgba(120, 132, 124, 0.22);
            --dash-accent: #0D9488;
            --dash-accent-soft: rgba(240, 253, 250, 0.85);
            --dash-positive: #047857;
            --dash-negative: #B91C1C;
            --dash-sidebar: #121820;
            --space-sm: 0.5rem;
            --space-md: 1rem;
            --space-lg: 1.5rem;
            --radius-md: 12px;
            --radius-lg: 14px;
        }
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap');
        html, body, [class*="css"] {
            font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
            font-size: 0.9375rem;
            line-height: 1.55;
            color: var(--dash-ink);
        }
        .stApp {
            background: var(--dash-bg);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, var(--dash-sidebar) 0%, #1A222C 100%);
            border-right: 1px solid rgba(180, 196, 188, 0.14);
        }
        [data-testid="stSidebar"] * {
            color: #DDE4E0 !important;
            line-height: 1.6;
        }
        [data-testid="stSidebar"] .stTextInput label,
        [data-testid="stSidebar"] .stSelectbox label {
            color: #A8B5AD !important;
            font-size: 0.8125rem !important;
        }
        [data-testid="stSidebar"] .stButton > button {
            background: var(--dash-accent) !important;
            color: #F0FDFA !important;
            border: 1px solid rgba(13, 148, 136, 0.45) !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background: #0F766E !important;
            border-color: #0F766E !important;
        }
        .sidebar-brand {
            font-family: 'IBM Plex Mono', ui-monospace, monospace;
            font-size: 0.6875rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--dash-accent) !important;
            margin-bottom: 0.15rem;
        }
        .sidebar-title {
            font-size: 1.125rem;
            font-weight: 700;
            color: #F3F5F4 !important;
            margin-bottom: var(--space-md);
        }
        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
            max-width: 1180px;
        }
        h1, h2, h3, h4, h5, h6 {
            color: var(--dash-ink) !important;
            font-weight: 600 !important;
            letter-spacing: -0.01em;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--dash-border) !important;
            border-radius: var(--radius-lg) !important;
            background: var(--dash-surface) !important;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--dash-border);
            border-radius: var(--radius-md);
            overflow: hidden;
        }
        [data-testid="stAlert"] {
            border-radius: var(--radius-md);
        }
        hr {
            border-color: var(--dash-border) !important;
            margin: var(--space-md) 0 !important;
        }
        .dashboard-hero {
            border: 1px solid rgba(13, 148, 136, 0.18);
            border-radius: var(--radius-lg);
            padding: var(--space-lg);
            background: var(--dash-surface);
            box-shadow: 0 8px 24px rgba(18, 24, 32, 0.05);
            margin-bottom: var(--space-md);
        }
        .dashboard-kicker {
            font-family: 'IBM Plex Mono', ui-monospace, monospace;
            font-size: 0.6875rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: #0D9488;
            margin-bottom: 0.35rem;
            font-weight: 600;
        }
        .dashboard-title {
            font-size: 1.75rem;
            font-weight: 700;
            line-height: 1.2;
            color: #121820;
        }
        .dashboard-subtitle {
            font-size: 0.9375rem;
            color: #4A5750;
            margin-top: 0.5rem;
            max-width: 62ch;
        }
        .status-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin: 0.85rem 0 0.2rem 0;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.35rem 0.75rem;
            border-radius: 6px;
            font-size: 0.8125rem;
            font-weight: 600;
            border: 1px solid var(--dash-border);
            background: var(--dash-surface);
            color: var(--dash-muted);
        }
        .status-pill.live {
            border-color: rgba(13, 148, 136, 0.32);
            background: rgba(236, 253, 249, 0.96);
            color: #0F766E;
        }
        .status-pill.openclaw-on {
            border-color: rgba(13, 148, 136, 0.32);
            background: rgba(236, 253, 249, 0.96);
            color: #115E59;
        }
        .status-pill.openclaw-off {
            border-color: rgba(120, 132, 124, 0.28);
            background: rgba(250, 251, 250, 0.96);
            color: #5C6B63;
        }
        .oc-badge {
            display: inline-block;
            margin-right: 0.35rem;
            padding: 0.12rem 0.45rem;
            border-radius: 6px;
            font-size: 0.6875rem;
            font-weight: 600;
            letter-spacing: 0.03em;
        }
        .oc-badge.ai { background: #0D9488; color: #F0FDFA; }
        .oc-badge.kw { background: #5C6B63; color: #F3F5F4; }
        .oc-badge.user { background: #047857; color: #ECFDF5; }
        .oc-badge.news { background: #B45309; color: #FFFBEB; }
        .oc-badge.ref { background: #6B7280; color: #F9FAFB; }
        .pipeline-flow {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 0.5rem 0 0.75rem;
        }
        .pipeline-step {
            flex: 1 1 140px;
            padding: 0.65rem 0.75rem;
            border-radius: 10px;
            border: 1px solid rgba(13, 148, 136, 0.16);
            background: rgba(240, 253, 250, 0.7);
            font-size: 0.8125rem;
            font-weight: 600;
            color: #134E4A;
        }
        .pick-card {
            border: 1px solid rgba(120, 132, 124, 0.2);
            border-radius: 14px;
            padding: 1rem 1.05rem;
            background: #FAFBFA;
            box-shadow: 0 8px 24px rgba(18, 24, 32, 0.05);
            min-height: 168px;
            transition: transform 0.18s ease-out, box-shadow 0.18s ease-out;
        }
        .pick-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 28px rgba(18, 24, 32, 0.08);
        }
        @media (prefers-reduced-motion: reduce) {
            .pick-card {
                transition: none;
            }
            .pick-card:hover {
                transform: none;
            }
        }
        .pick-rank {
            font-family: 'IBM Plex Mono', ui-monospace, monospace;
            font-size: 0.6875rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--dash-subtle);
            font-weight: 600;
        }
        .pick-symbol {
            font-family: 'IBM Plex Mono', ui-monospace, monospace;
            font-size: 1.25rem;
            font-weight: 600;
            color: #121820;
            margin: 0.15rem 0 0.35rem 0;
        }
        .pick-score {
            font-family: 'IBM Plex Mono', ui-monospace, monospace;
            font-size: 1.625rem;
            font-weight: 600;
            line-height: 1;
        }
        .pick-score.pos { color: #047857; }
        .pick-score.neg { color: #B91C1C; }
        .pick-score.neu { color: #5C6B63; }
        .reason-card {
            border: 1px solid rgba(120, 132, 124, 0.2);
            border-radius: 14px;
            padding: 1rem;
            background: #FAFBFA;
            box-shadow: 0 8px 24px rgba(18, 24, 32, 0.04);
            min-height: 220px;
        }
        .section-surface {
            border: 1px solid rgba(120, 132, 124, 0.18);
            border-radius: 14px;
            background: #FAFBFA;
            padding: 0.2rem 0.4rem;
            box-shadow: 0 8px 24px rgba(18, 24, 32, 0.03);
        }
        div[data-testid="stMetric"] {
            background: #FAFBFA;
            border: 1px solid rgba(120, 132, 124, 0.18);
            border-radius: 12px;
            padding: 0.75rem 0.85rem;
            box-shadow: 0 6px 18px rgba(18, 24, 32, 0.03);
        }
        div[data-testid="stMetric"] label {
            color: #5C6B63 !important;
            font-size: 0.8125rem !important;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            font-family: 'IBM Plex Mono', ui-monospace, monospace;
            color: #121820 !important;
            font-weight: 600 !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.25rem;
            border-bottom: 1px solid var(--dash-border);
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            padding: 0.5rem 0.875rem;
            font-weight: 600;
            font-size: 0.875rem;
            color: var(--dash-muted);
        }
        .stTabs [aria-selected="true"] {
            color: var(--dash-accent) !important;
            border-bottom: 2px solid var(--dash-accent) !important;
        }
        .guide-card {
            border-left: 3px solid var(--dash-accent);
            padding: 0.75rem 1rem;
            margin: 0.5rem 0 1rem 0;
            background: var(--dash-accent-soft);
            border-radius: 0 var(--radius-md) var(--radius-md) 0;
            color: var(--dash-muted);
            font-size: 0.875rem;
            line-height: 1.6;
            max-width: 72ch;
        }
        .guide-card-title {
            font-weight: 600;
            color: #115E59;
            margin-bottom: 0.35rem;
            font-size: 0.9375rem;
        }
        .score-badge {
            display: inline-block;
            padding: 0.15rem 0.55rem;
            border-radius: 6px;
            font-size: 0.6875rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            font-family: 'IBM Plex Mono', ui-monospace, monospace;
        }
        .score-badge.strong { background: #047857; color: #ECFDF5; }
        .score-badge.positive { background: #0D9488; color: #F0FDFA; }
        .score-badge.risk { background: #B91C1C; color: #FEF2F2; }
        .score-badge.weak { background: #B45309; color: #FFFBEB; }
        .score-badge.neutral { background: #5C6B63; color: #F3F5F4; }
        .platform-chip {
            display: inline-block;
            margin: 0.15rem 0.35rem 0 0;
            padding: 0.15rem 0.5rem;
            border-radius: 6px;
            background: rgba(120, 132, 124, 0.1);
            font-size: 0.75rem;
            font-family: 'IBM Plex Mono', ui-monospace, monospace;
        }
        .platform-chip-label { font-weight: 500; }
        .trend-up { color: var(--dash-positive); font-size: 1rem; }
        .trend-down { color: var(--dash-negative); font-size: 1rem; }
        .trend-flat { color: var(--dash-subtle); font-size: 0.75rem; }
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


def _load_latest_monthly_training(
    report_dir: str,
) -> tuple[pd.DataFrame, Dict[str, object]]:
    return load_latest_monthly_training(report_dir)


def _platform_contributions(
    sentiment_df: pd.DataFrame, lookback_days: int = 30
) -> pd.DataFrame:
    if sentiment_df.empty:
        return pd.DataFrame()
    view = sentiment_df.copy()
    view["trade_date"] = pd.to_datetime(view["trade_date"], errors="coerce")
    view["sentiment_score"] = pd.to_numeric(
        view.get("sentiment_score", None), errors="coerce"
    )
    base = view.dropna(subset=["trade_date", "sentiment_score"]).copy()
    if base.empty:
        return pd.DataFrame()

    lookback_days = max(1, int(lookback_days))
    # compute per-(symbol,platform) last seen date, then compute observations within that pair-specific window
    last_seen = (
        base.groupby(["symbol", "platform"], as_index=False)["trade_date"]
        .max()
        .rename(columns={"trade_date": "last_seen"})
    )
    merged = base.merge(last_seen, on=["symbol", "platform"], how="left")
    merged["window_start"] = merged["last_seen"] - pd.to_timedelta(
        lookback_days - 1, unit="D"
    )
    in_window = merged[
        (merged["trade_date"] >= merged["window_start"])
        & (merged["trade_date"] <= merged["last_seen"])
    ].copy()

    rate_df = in_window.groupby(["symbol", "platform"], as_index=False).agg(
        observations=("sentiment_score", "size"),
        non_zero_observations=("sentiment_score", lambda s: (s != 0).sum()),
    )
    rate_df = rate_df.merge(last_seen, on=["symbol", "platform"], how="left")
    rate_df["non_zero_rate"] = (
        rate_df["non_zero_observations"]
        / rate_df["observations"].where(rate_df["observations"] != 0, pd.NA)
    ).fillna(0.0)
    rate_df["non_zero_rate_pct"] = (rate_df["non_zero_rate"] * 100).round(2)

    # For each (symbol, platform) pick the most recent non-null sentiment_score
    view = view.sort_values("trade_date")
    # convert to numeric; by default treat 0 as missing unless user opted-in
    include_zero = False
    try:
        include_zero = bool(st.session_state.get("include_zero_scores", False))
    except Exception:
        include_zero = False
    if not include_zero:
        view.loc[view["sentiment_score"] == 0.0, "sentiment_score"] = pd.NA
    # keep last non-null per (symbol, platform)
    non_null = view.dropna(subset=["sentiment_score"]).copy()
    if non_null.empty:
        return pd.DataFrame()
    last_per_pair = non_null.drop_duplicates(subset=["symbol", "platform"], keep="last")
    grouped = (
        last_per_pair.groupby(["symbol", "platform"], as_index=False)["sentiment_score"]
        .mean()
        .rename(columns={"sentiment_score": "platform_score"})
    )
    grouped["abs_score"] = grouped["platform_score"].abs()
    grouped["weight"] = grouped.groupby("symbol")["abs_score"].transform(
        lambda x: x / x.sum() if x.sum() != 0 else 0.0
    )
    grouped["weight_pct"] = (grouped["weight"] * 100).round(2)
    grouped = grouped.merge(
        rate_df[
            [
                "symbol",
                "platform",
                "observations",
                "non_zero_rate",
                "non_zero_rate_pct",
                "last_seen",
            ]
        ],
        on=["symbol", "platform"],
        how="left",
    )
    grouped["observations"] = (
        pd.to_numeric(grouped["observations"], errors="coerce").fillna(0).astype(int)
    )
    grouped["non_zero_rate"] = pd.to_numeric(
        grouped["non_zero_rate"], errors="coerce"
    ).fillna(0.0)
    grouped["non_zero_rate_pct"] = (grouped["non_zero_rate"] * 100).round(2)
    return grouped.sort_values(["symbol", "weight_pct"], ascending=[True, False])


def _platform_scores_radar(sentiment_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if sentiment_df.empty:
        return pd.DataFrame()
    view = sentiment_df.copy()
    view["trade_date"] = pd.to_datetime(view["trade_date"], errors="coerce")
    latest_date = view["trade_date"].max()
    view = view[(view["trade_date"] == latest_date) & (view["symbol"] == symbol)].copy()
    if view.empty:
        return pd.DataFrame()
    # ensure numeric; treat 0 as missing by default (0 often indicates no signal)
    view["sentiment_score"] = pd.to_numeric(
        view.get("sentiment_score", None), errors="coerce"
    )
    include_zero = False
    try:
        include_zero = bool(st.session_state.get("include_zero_scores", False))
    except Exception:
        include_zero = False
    if not include_zero:
        view.loc[view["sentiment_score"] == 0.0, "sentiment_score"] = pd.NA
    # use post_count as weight if available
    if "post_count" in view.columns:
        view["post_count"] = pd.to_numeric(
            view.get("post_count", 1), errors="coerce"
        ).fillna(1)

        def _wmean(g):
            denom = g["post_count"].sum()
            return (
                (g["sentiment_score"] * g["post_count"]).sum() / denom
                if denom
                else g["sentiment_score"].mean()
            )

        tmp = view.dropna(subset=["sentiment_score"]).copy()
        if tmp.empty:
            grouped = pd.DataFrame(columns=["platform", "sentiment_score"])
        elif "post_count" in tmp.columns:
            tmp = tmp.copy()
            tmp["_weighted"] = tmp["sentiment_score"] * tmp["post_count"]
            sums = tmp.groupby("platform")["post_count"].sum()
            numer = tmp.groupby("platform")["_weighted"].sum()
            series = numer / sums
            grouped = pd.DataFrame(
                {"platform": list(series.index), "sentiment_score": list(series.values)}
            )
        else:
            series = tmp.groupby("platform")["sentiment_score"].mean()
            grouped = pd.DataFrame(
                {"platform": list(series.index), "sentiment_score": list(series.values)}
            )
    else:
        grouped = (
            view.dropna(subset=["sentiment_score"])
            .groupby("platform", as_index=False)["sentiment_score"]
            .mean()
        )
    grouped["abs_score"] = grouped["sentiment_score"].abs()
    return grouped


def _score_badge(score: float) -> str:
    lang = st.session_state.get("lang", "zh") if hasattr(st, "session_state") else "zh"
    labels = {
        "en": ("STRONG", "POSITIVE", "RISK", "WEAK", "NEUTRAL"),
        "zh": ("强势", "偏多", "风险", "偏弱", "中性"),
    }
    strong, positive, risk, weak, neutral = labels.get(lang, labels["en"])
    if score >= 0.35:
        return f"<span class='score-badge strong'>{strong}</span>"
    if score >= 0.15:
        return f"<span class='score-badge positive'>{positive}</span>"
    if score <= -0.35:
        return f"<span class='score-badge risk'>{risk}</span>"
    if score <= -0.15:
        return f"<span class='score-badge weak'>{weak}</span>"
    return f"<span class='score-badge neutral'>{neutral}</span>"


def _render_info_box(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="guide-card">
            <div class="guide-card-title">{title}</div>
            <div>{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _parse_platform_scores(raw_value) -> Dict[str, float]:
    return parse_platform_scores(raw_value)


def _latest_report_meta(report_dir: str) -> tuple[str, str]:
    path = _latest_file(str(Path(report_dir) / "realtime_picks_*.csv"))
    if not path:
        return "", ""
    p = Path(path)
    ts = p.stem.replace("realtime_picks_", "")
    display = ts
    if len(ts) >= 15 and ts[8] == "_":
        display = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}:{ts[13:15]}"
    return path, display


def _render_status_strip(
    report_dir: str,
    picks_count: int,
    alerts_count: int,
    platform_count: int,
    *,
    openclaw_connected: bool | None = None,
) -> None:
    _, report_time = _latest_report_meta(report_dir)
    pills = []
    if openclaw_connected is not None:
        oc_cls = "openclaw-on" if openclaw_connected else "openclaw-off"
        oc_label = t("openclaw_connected") if openclaw_connected else t("openclaw_disconnected")
        pills.append(
            f"<span class='status-pill {oc_cls}'>OpenClaw · {oc_label}</span>"
        )
    if report_time:
        pills.append(
            f"<span class='status-pill live'>{t('status_last_report')}: {report_time}</span>"
        )
    pills.append(
        f"<span class='status-pill'>{t('realtime_picks')}: {picks_count}</span>"
    )
    pills.append(
        f"<span class='status-pill'>{t('score_alerts')}: {alerts_count}</span>"
    )
    pills.append(
        f"<span class='status-pill'>{t('platform_label')}: {platform_count}</span>"
    )
    st.markdown(
        f"<div class='status-strip'>{''.join(pills)}</div>", unsafe_allow_html=True
    )


def _render_pick_leaderboard(picks_df: pd.DataFrame) -> None:
    if picks_df.empty:
        st.info(t("no_realtime_picks"))
        return

    view = picks_df.copy()
    if "avg_score" not in view.columns:
        st.dataframe(view, use_container_width=True)
        return

    view["avg_score"] = pd.to_numeric(view["avg_score"], errors="coerce").fillna(0.0)
    view = view.sort_values("avg_score", ascending=False).reset_index(drop=True)
    cols = st.columns(min(3, len(view)))

    for idx, row in view.head(3).iterrows():
        symbol = str(row.get("symbol", ""))
        score = float(row.get("avg_score", 0.0))
        score_class = "pos" if score > 0.05 else "neg" if score < -0.05 else "neu"
        platform_scores = _parse_platform_scores(row.get("platform_scores", ""))
        platform_html = ""
        if platform_scores:
            chips = []
            for platform, pscore in sorted(
                platform_scores.items(), key=lambda x: abs(x[1]), reverse=True
            )[:4]:
                chips.append(_platform_chip_html(platform, pscore))
            platform_html = "".join(chips)
        else:
            platform_html = (
                f"<span style='color:#5C6B63;font-size:0.8125rem;'>"
                f"{t('no_platform_scores')}</span>"
            )

        with cols[idx]:
            st.markdown(
                f"""
                <div class="pick-card">
                    <div class="pick-rank">{t('rank_label')} #{idx + 1}</div>
                    <div class="pick-symbol">{_symbol_label(symbol)}</div>
                    <div class="pick-score {score_class}">{score:+.4f}</div>
                    <div style="margin-top:0.45rem;">{_score_badge(score)}</div>
                    <div style="margin-top:0.75rem;">{platform_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander(t("key_fields"), expanded=False):
        st.caption(t("key_fields_help"))
        detail = build_picks_detail_table(view, _ui_lang())
        st.dataframe(detail, use_container_width=True, hide_index=True)


def _trend_arrow(score: float) -> str:
    if score >= 0.15:
        return "<span class='trend-up'>▲</span>"
    if score <= -0.15:
        return "<span class='trend-down'>▼</span>"
    return "<span class='trend-flat'>■</span>"


def _comment_preview_label(platform: str, score: float, text: str, max_len: int = 40) -> str:
    preview = text if len(text) <= max_len else f"{text[:max_len]}…"
    return f"{_platform_label(platform)} · {score:+.2f} · {preview}"


def _render_comment_highlights(
    comments_df: pd.DataFrame,
    *,
    key_prefix: str,
    empty_message: str | None = None,
) -> None:
    if comments_df.empty:
        if empty_message:
            st.caption(empty_message)
        return

    st.caption(t("click_to_expand"))
    for idx, (_, row) in enumerate(comments_df.iterrows()):
        platform = str(row.get("platform", "") or "")
        score = float(row.get("ai_score", 0) or 0)
        full_text = str(row.get("full_text") or row.get("display_text") or "")
        if not full_text:
            continue
        label = _comment_preview_label(platform, score, full_text)
        with st.expander(f"{label} · #{idx + 1}", expanded=False):
            st.markdown(_comment_badges_html(row), unsafe_allow_html=True)
            st.markdown(full_text)
            post_time = str(row.get("post_time", "") or "").strip()
            if post_time:
                st.caption(f"{t('col_post_time')}: {post_time}")
            url = str(row.get("url", "") or "")
            if url.startswith("http"):
                st.markdown(f"[{t('col_url')}]({url})")


def _render_reason_cards(
    raw_df: pd.DataFrame,
    picks_df: pd.DataFrame,
    sentiment_df: pd.DataFrame,
    lookback_days: int = 30,
) -> None:
    if picks_df.empty:
        st.info(t("no_reason_cards"))
        return

    lang = st.session_state.get("lang", "zh")
    view = picks_df.copy()
    view["avg_score"] = pd.to_numeric(view.get("avg_score"), errors="coerce").fillna(
        0.0
    )
    view = view.sort_values("avg_score", ascending=False).reset_index(drop=True)
    symbols = view["symbol"].dropna().tolist()

    for rank, symbol in enumerate(symbols, start=1):
        pick_row = view[view["symbol"] == symbol].head(1)
        avg_score = float(pick_row["avg_score"].iloc[0]) if not pick_row.empty else 0.0
        contrib = build_pick_contribution(
            symbol, picks_df, raw_df, sentiment_df, lookback_days
        )
        st.markdown(f"##### #{rank} {_symbol_label(symbol)}")
        st.markdown(build_pick_narrative(symbol, avg_score, contrib, raw_df, lang=lang))

        stats = evidence_stats(raw_df, symbol)
        st.caption(_evidence_caption(stats))
        if stats["valid"] < 5:
            st.warning(t("sample_low_warning"))
        if stats["valid"] < 3:
            st.info(t("comments_few_hint"))

        top_rows = top_comment_rows(raw_df, symbol, top_n=10, include_reference=True)
        pos_items = top_rows["positive"]
        neg_items = top_rows["negative"]
        ref_items = top_rows["reference"]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{t('positive_highlight')}** ({len(pos_items)})")
            _render_comment_highlights(
                pos_items,
                key_prefix=f"pick_pos_{symbol}",
                empty_message=t("no_valid_comments"),
            )
        with c2:
            st.markdown(f"**{t('negative_highlight')}** ({len(neg_items)})")
            _render_comment_highlights(
                neg_items,
                key_prefix=f"pick_neg_{symbol}",
                empty_message=t("no_valid_comments"),
            )
        if not ref_items.empty:
            st.markdown(f"**{t('reference_comments')}** ({len(ref_items)})")
            _render_comment_highlights(
                ref_items,
                key_prefix=f"pick_ref_{symbol}",
                empty_message=None,
            )

        if not contrib.empty:
            drivers = contrib[contrib["platform_score"].abs() > 0.001].head(4)
            if not drivers.empty:
                chips = []
                for _, dr in drivers.iterrows():
                    chips.append(
                        _platform_chip_html(
                            str(dr["platform"]),
                            float(dr["platform_score"]),
                            suffix=f" · {dr['weight_pct']:.0f}%",
                        )
                    )
                st.markdown("".join(chips), unsafe_allow_html=True)
        st.divider()


def main() -> None:
    _bootstrap_openclaw_env()
    st.set_page_config(
        page_title=LANG.get("zh", {}).get("page_title", "OpenClaw"),
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_dashboard_styles()
    if "lang" not in st.session_state:
        st.session_state["lang"] = "zh"

    with st.sidebar:
        st.markdown(
            "<div class='sidebar-brand'>OpenClaw</div>"
            "<div class='sidebar-title'>AI Picks</div>",
            unsafe_allow_html=True,
        )
        opts = [
            ("en", LANG.get("en", {}).get("language_en", "English")),
            ("zh", LANG.get("zh", {}).get("language_zh", "中文")),
        ]
        cur = st.session_state.get("lang", "zh")
        idx = 0 if cur == "en" else 1
        sel = st.selectbox(
            t("language_label"),
            options=opts,
            index=idx,
            key="_lang_display",
            format_func=lambda x: x[1],
        )
        if isinstance(sel, tuple):
            st.session_state["lang"] = sel[0]

        if st.button(t("refresh_data"), use_container_width=True):
            st.rerun()

        _render_openclaw_sidebar()

        st.markdown(f"#### {t('sidebar_paths')}")
        report_dir = st.text_input(t("report_dir"), "data/reports")
        raw_dir = st.text_input(t("raw_dir"), "data/raw")
        memory_dir = st.text_input(t("memory_dir"), "data/memory")

        with st.expander(t("quick_start"), expanded=False):
            st.markdown(t("tutorial_markdown"))

    picks_df = _load_latest_realtime_picks(report_dir)
    alerts_df = _load_latest_alerts(report_dir)
    sentiment_df = _load_sentiment_history(
        str(Path(memory_dir) / "sentiment_history.jsonl")
    )
    raw_df = _load_latest_raw_posts(raw_dir)
    platform_count = 0 if sentiment_df.empty else sentiment_df["platform"].nunique()

    st.markdown(
        f"""
        <div class="dashboard-hero">
            <div class="dashboard-kicker">OpenClaw AI</div>
            <div class="dashboard-title">{t('header_title')}</div>
            <div class="dashboard-subtitle">{t('hero_tagline')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_info_box(t("user_guide_title"), t("user_guide_body"))
    oc_probe = _openclaw_probe()
    _render_status_strip(
        report_dir,
        len(picks_df),
        len(alerts_df),
        platform_count,
        openclaw_connected=bool(oc_probe.get("connected")),
    )

    tab_picks, tab_openclaw, tab_sentiment, tab_comments, tab_eval = st.tabs(
        [
            t("tab_picks"),
            t("tab_openclaw"),
            t("tab_sentiment"),
            t("tab_comments"),
            t("tab_eval"),
        ]
    )

    with tab_picks:
        st.markdown(f"#### {t('realtime_picks')}")
        _render_pick_leaderboard(picks_df)

        st.markdown(f"#### {t('score_alerts')}")
        if alerts_df.empty:
            st.info(t("no_alerts"))
        else:
            st.dataframe(alerts_df, use_container_width=True, hide_index=True)

        st.markdown(f"#### {t('pick_reason_cards')}")
        if picks_df.empty:
            st.info(t("run_realtime_daily_first"))
        else:
            _render_reason_cards(raw_df, picks_df, sentiment_df, lookback_days=30)

    with tab_openclaw:
        _render_openclaw_tab(raw_df, picks_df, report_dir)

    with tab_sentiment:
        _render_info_box(t("guide_trend_title"), t("guide_trend_body"))
        st.markdown(f"#### {t('sentiment_trend')}")
        with st.container(border=True):
            if not sentiment_df.empty:
                df = sentiment_df.copy()
                df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
                df["sentiment_score"] = pd.to_numeric(
                    df.get("sentiment_score", None), errors="coerce"
                )
                include_zero = False
                try:
                    include_zero = bool(
                        st.session_state.get("include_zero_scores", False)
                    )
                except Exception:
                    include_zero = False
                if not include_zero:
                    df.loc[df["sentiment_score"] == 0.0, "sentiment_score"] = pd.NA

                df["month"] = df["trade_date"].dt.to_period("M").astype(str)

                if "post_count" in df.columns:
                    df["post_count"] = pd.to_numeric(
                        df.get("post_count", 1), errors="coerce"
                    ).fillna(1)
                    tmp2 = df.dropna(subset=["sentiment_score"]).copy()
                    if tmp2.empty:
                        grouped = pd.DataFrame(
                            columns=["month", "platform", "sentiment_score"]
                        )
                    else:
                        tmp2 = tmp2.copy()
                        tmp2["_weighted"] = tmp2["sentiment_score"] * tmp2["post_count"]
                        sums = tmp2.groupby(["month", "platform"])["post_count"].sum()
                        numer = tmp2.groupby(["month", "platform"])["_weighted"].sum()
                        series = numer / sums
                        idx = pd.DataFrame(
                            list(series.index), columns=["month", "platform"]
                        )
                        grouped = pd.concat(
                            [
                                idx.reset_index(drop=True),
                                pd.DataFrame({"sentiment_score": list(series.values)}),
                            ],
                            axis=1,
                        )
                else:
                    grouped = (
                        df.dropna(subset=["sentiment_score"])
                        .groupby(["month", "platform"], as_index=False)[
                            "sentiment_score"
                        ]
                        .mean()
                    )

                if grouped.empty:
                    st.info(t("no_sentiment_history"))
                else:
                    counts = (
                        df.dropna(subset=["sentiment_score"])
                        .groupby("platform")
                        .size()
                        .reset_index(name="samples")
                    )
                    cols = st.columns([1, 1, 1])
                    min_samples = cols[0].number_input(
                        "Min samples per platform",
                        min_value=0,
                        value=1,
                        step=1,
                    )
                    show_counts = cols[1].checkbox(
                        "Show platform sample counts", value=True
                    )
                    include_zero = cols[2].checkbox(
                        "Include zero scores (treat 0 as valid)", value=True
                    )
                    try:
                        st.session_state["include_zero_scores"] = bool(include_zero)
                    except Exception:
                        pass

                    valid_platforms = counts[counts["samples"] >= int(min_samples)][
                        "platform"
                    ].tolist()
                    filtered = grouped[grouped["platform"].isin(valid_platforms)].copy()
                    csv_bytes = filtered.to_csv(index=False).encode("utf-8")
                    cols[2].download_button(
                        label="Download CSV",
                        data=csv_bytes,
                        file_name="agg_monthly_filtered.csv",
                        mime="text/csv",
                    )

                    if show_counts:
                        st.markdown(
                            "**Platform sample counts**: "
                            + ", ".join(
                                [
                                    f"{_platform_label(str(r['platform']))}={r['samples']}"
                                    for _, r in counts.iterrows()
                                ]
                            )
                        )

                    if filtered.empty:
                        st.warning(
                            "No platforms remain after filtering; lower Min samples."
                        )
                    else:
                        chart_df = label_platform_column(filtered, _ui_lang())
                        chart = (
                            alt.Chart(chart_df)
                            .mark_line(point=True, strokeWidth=2.4)
                            .encode(
                                x=alt.X("month:N", title=t("month")),
                                y=alt.Y(
                                    "sentiment_score:Q",
                                    title=t("sentiment_score_label"),
                                ),
                                color=alt.Color(
                                    "platform:N",
                                    scale=alt.Scale(range=_DASH_COLORS),
                                    title=t("platform_label"),
                                ),
                                tooltip=["month", "platform", "sentiment_score"],
                            )
                            .properties(title=t("sentiment_trend"), height=280)
                        )
                        st.altair_chart(
                            _configure_chart(chart), use_container_width=True
                        )
            else:
                st.info(t("no_sentiment_history"))

        _render_info_box(t("guide_contrib_title"), t("guide_contrib_body"))
        st.markdown(f"#### {t('platform_contribution')}")
        with st.container(border=True):
            lookback_days = st.number_input(
                t("lookback_days_non_zero"),
                min_value=1,
                value=30,
                step=1,
            )
            pick_symbols = (
                sorted(picks_df["symbol"].unique()) if not picks_df.empty else []
            )
            hist_symbols = (
                sorted(sentiment_df["symbol"].unique())
                if not sentiment_df.empty
                else []
            )
            symbol_options = sorted(set(pick_symbols + hist_symbols))
            if not symbol_options:
                st.info(t("no_contribution_data"))
            else:
                symbol = st.selectbox(
                    t("select_symbol_for_contribution"),
                    symbol_options,
                )
                contrib_df = build_pick_contribution(
                    symbol,
                    picks_df,
                    raw_df,
                    sentiment_df,
                    lookback_days=int(lookback_days),
                )
                if contrib_df.empty:
                    st.info(t("no_contribution_data"))
                else:
                    avg_score = 0.0
                    if not picks_df.empty:
                        pr = picks_df[picks_df["symbol"] == symbol].head(1)
                        if not pr.empty:
                            avg_score = float(
                                pd.to_numeric(pr["avg_score"], errors="coerce").fillna(
                                    0
                                )
                            )
                    lang = st.session_state.get("lang", "zh")
                    st.markdown(
                        build_pick_narrative(
                            symbol, avg_score, contrib_df, raw_df, lang=lang
                        )
                    )
                    stats = evidence_stats(raw_df, symbol)
                    st.caption(_evidence_caption(stats))
                    if stats["valid"] < 8:
                        st.warning(t("sample_low_warning"))

                    display_df = label_platform_column(contrib_df, _ui_lang())[
                        [
                            "platform",
                            "platform_score",
                            "config_weight",
                            "weighted_contrib",
                            "weight_pct",
                            "observations",
                            "direction",
                        ]
                    ].rename(
                        columns={
                            "platform": t("col_platform"),
                            "platform_score": t("col_platform_score"),
                            "config_weight": t("col_config_weight"),
                            "weighted_contrib": t("col_weighted_contrib"),
                            "weight_pct": t("col_weight_pct"),
                            "observations": t("col_observations"),
                            "direction": t("col_direction"),
                        }
                    )
                    st.dataframe(display_df, use_container_width=True, hide_index=True)

                    chart_view = contrib_df[
                        contrib_df["platform_score"].abs() > 0.001
                    ].copy()
                    if chart_view.empty:
                        chart_view = contrib_df.copy()
                    chart_view = label_platform_column(chart_view, _ui_lang())
                    chart_view["bar_color"] = chart_view["platform_score"].apply(
                        lambda s: "bull"
                        if s > 0.05
                        else "bear"
                        if s < -0.05
                        else "flat"
                    )
                    color_scale = _SENTIMENT_BAR_SCALE
                    bar = (
                        alt.Chart(chart_view)
                        .mark_bar(cornerRadiusEnd=6)
                        .encode(
                            x=alt.X(
                                "weighted_contrib:Q",
                                title=t("col_weighted_contrib"),
                            ),
                            y=alt.Y("platform:N", sort="-x", title=None),
                            color=alt.Color(
                                "bar_color:N",
                                scale=color_scale,
                                title=t("col_direction"),
                            ),
                            tooltip=[
                                "platform",
                                "platform_score",
                                "config_weight",
                                "weighted_contrib",
                                "weight_pct",
                                "observations",
                            ],
                        )
                        .properties(title=t("platform_contribution"), height=280)
                    )
                    st.altair_chart(
                        _configure_chart(bar), use_container_width=True
                    )

        _render_info_box(t("guide_snapshot_title"), t("guide_snapshot_body"))
        st.markdown(f"#### {t('platform_snapshot')}")
        pick_symbols = sorted(picks_df["symbol"].unique()) if not picks_df.empty else []
        hist_symbols = (
            sorted(sentiment_df["symbol"].unique()) if not sentiment_df.empty else []
        )
        snapshot_options = sorted(set(pick_symbols + hist_symbols))
        snapshot_symbol = st.selectbox(
            t("select_symbol_for_radar"),
            snapshot_options if snapshot_options else [""],
        )
        with st.container(border=True):
            if not snapshot_symbol:
                st.info(t("no_radar_data"))
            else:
                snap = build_pick_contribution(
                    snapshot_symbol,
                    picks_df,
                    raw_df,
                    sentiment_df,
                    lookback_days=30,
                )
                if snap.empty:
                    st.info(t("no_radar_data"))
                else:
                    snap_display = label_platform_column(snap, _ui_lang())
                    snap_display["sentiment_label"] = snap_display[
                        "platform_score"
                    ].apply(lambda s: f"{s:+.3f}")
                    snap_display["bar_color"] = snap_display["platform_score"].apply(
                        lambda s: "bull"
                        if s > 0.05
                        else "bear"
                        if s < -0.05
                        else "flat"
                    )
                    color_scale = _SENTIMENT_BAR_SCALE
                    snap_chart = (
                        alt.Chart(snap_display)
                        .mark_bar(cornerRadiusEnd=4)
                        .encode(
                            x=alt.X(
                                "platform_score:Q", title=t("sentiment_score_label")
                            ),
                            y=alt.Y("platform:N", sort="-x", title=t("platform_label")),
                            color=alt.Color(
                                "bar_color:N",
                                scale=color_scale,
                                title=t("col_direction"),
                            ),
                            tooltip=[
                                "platform",
                                "platform_score",
                                "observations",
                                "weight_pct",
                            ],
                        )
                        .properties(height=max(220, 36 * len(snap_display)))
                    )
                    st.altair_chart(
                        _configure_chart(snap_chart), use_container_width=True
                    )
                    st.dataframe(
                        snap_display[
                            [
                                "platform",
                                "platform_score",
                                "observations",
                                "weight_pct",
                                "direction",
                            ]
                        ].rename(
                            columns={
                                "platform": t("col_platform"),
                                "platform_score": t("col_platform_score"),
                                "observations": t("col_observations"),
                                "weight_pct": t("col_weight_pct"),
                                "direction": t("col_direction"),
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

    with tab_comments:
        _render_info_box(t("guide_comments_title"), t("guide_comments_body"))
        st.markdown(f"#### {t('top_comments')}")
        if raw_df.empty:
            st.info(t("no_raw_posts"))
        else:
            sel_symbol = st.selectbox(
                t("select_symbol"), sorted(raw_df["symbol"].unique())
            )
            stats = evidence_stats(raw_df, sel_symbol)
            st.caption(_evidence_caption(stats))
            if stats["valid"] < 5:
                st.warning(t("sample_low_warning"))
            if stats["valid"] < 3:
                st.info(t("comments_few_hint"))

            top_rows = top_comment_rows(
                raw_df, sel_symbol, top_n=12, include_reference=True, ref_n=10
            )
            comment_cols = st.columns(2)
            with comment_cols[0]:
                st.markdown(
                    f"**{t('positive_highlight')}** ({len(top_rows['positive'])})"
                )
                _render_comment_highlights(
                    top_rows["positive"],
                    key_prefix=f"tab_pos_{sel_symbol}",
                    empty_message=None,
                )
                if top_rows["positive"].empty:
                    st.info(t("no_valid_comments"))
            with comment_cols[1]:
                st.markdown(
                    f"**{t('negative_highlight')}** ({len(top_rows['negative'])})"
                )
                _render_comment_highlights(
                    top_rows["negative"],
                    key_prefix=f"tab_neg_{sel_symbol}",
                    empty_message=None,
                )
                if top_rows["negative"].empty:
                    st.info(t("no_valid_comments"))
            if not top_rows["reference"].empty:
                st.markdown(
                    f"**{t('reference_comments')}** ({len(top_rows['reference'])})"
                )
                _render_comment_highlights(
                    top_rows["reference"],
                    key_prefix=f"tab_ref_{sel_symbol}",
                    empty_message=None,
                )

    with tab_eval:
        st.markdown(f"#### {t('evaluation')}")
        price_source_mode = st.radio(
            t("price_source"),
            LANG.get(st.session_state.get("lang", "zh"), LANG["en"]).get(
                "price_options", []
            ),
            horizontal=True,
            index=0,
        )
        uploaded_price_file = st.file_uploader(
            t("upload_label"), type=["csv"], key="price_upload"
        )
        price_csv = st.text_input(
            t("local_csv_path"), "data/reports/price_history_cache.csv"
        )
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
                signal_df = (
                    pd.read_json(signals_path, lines=True)
                    if Path(signals_path).exists()
                    else pd.DataFrame()
                )
                if not signal_df.empty:
                    signal_df["trade_date"] = pd.to_datetime(
                        signal_df["trade_date"], errors="coerce"
                    )
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
                    symbols = (
                        sorted(signal_df["symbol"].dropna().unique())
                        if not signal_df.empty
                        else []
                    )
                    price_df = fetch_prices_with_timeout(symbols, start_date, end_date)
                    if price_df.empty:
                        st.warning(t("yahoo_no_prices"))
                        return
                merged, summary = evaluate_signals(
                    signal_df, price_df, start_date or None, end_date or None
                )
                st.markdown(
                    f"**{t('eval_accuracy')}**: {summary.accuracy:.2%} | **{t('eval_avg_return')}**: {summary.avg_return:.4%} | "
                    f"**{t('eval_win_rate')}**: {summary.win_rate:.2%} | **{t('eval_sharpe_like')}**: {summary.sharpe_like:.4f}"
                )
                if not merged.empty:
                    st.dataframe(
                        merged[
                            ["trade_date", "symbol", "action", "next_return", "correct"]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
            except Exception as e:
                st.error(t("evaluation_failed").format(error=e))

        st.markdown(f"#### {t('monthly_training')}")
        lang = st.session_state.get("lang", "zh")
        method_title, method_body = monthly_methodology_text(lang)
        with st.expander(method_title, expanded=True):
            st.markdown(method_body)
        train_months = st.slider(
            t("training_lookback"), min_value=1, max_value=24, value=6
        )
        run_monthly_train = st.button(t("refresh_monthly"))

        signal_history_df = load_training_history(memory_dir)
        monthly_df, monthly_summary = _load_latest_monthly_training(report_dir)

        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric(t("realtime_picks"), len(picks_df))
        with summary_cols[1]:
            st.metric(t("score_alerts"), len(alerts_df))
        with summary_cols[2]:
            st.metric(
                t("sentiment_trend"),
                0 if sentiment_df.empty else sentiment_df["platform"].nunique(),
            )
        with summary_cols[3]:
            st.metric(t("monthly_training"), 0 if monthly_df.empty else len(monthly_df))

        if run_monthly_train:
            if signal_history_df.empty:
                st.info(t("no_signal_history"))
            else:
                signal_history_df["trade_date"] = pd.to_datetime(
                    signal_history_df["trade_date"], errors="coerce"
                )
                signal_history_df = signal_history_df.dropna(
                    subset=["trade_date", "symbol"]
                )
                if signal_history_df.empty:
                    st.info(t("valid_dates_missing"))
                else:
                    max_trade_date = signal_history_df["trade_date"].max()
                    min_trade_date = (
                        max_trade_date - pd.DateOffset(months=max(1, train_months) - 1)
                    ).normalize()
                    symbols = sorted(signal_history_df["symbol"].dropna().unique())
                    try:
                        if price_source_mode == "Upload CSV":
                            train_price_df = _load_uploaded_price_frame(
                                uploaded_price_file
                            )
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
                                try:
                                    train_price_df = load_prices(price_csv)
                                except Exception:
                                    train_price_df = pd.DataFrame()
                                if train_price_df.empty:
                                    raise ValueError(t("empty_yahoo_prices"))
                        monthly_df, monthly_summary_obj = build_monthly_training_frame(
                            signal_history_df,
                            train_price_df,
                            months=train_months,
                        )
                        outputs = save_monthly_training_report(
                            report_dir, monthly_df, monthly_summary_obj
                        )
                        monthly_df, monthly_summary = _load_latest_monthly_training(
                            report_dir
                        )
                        st.success(f"{t('monthly_saved')}: {outputs['csv']}")
                    except Exception as e:
                        st.error(t("monthly_failed").format(error=e))

        with st.container(border=True):
            if monthly_df.empty:
                st.info(t("no_monthly_report"))
            else:
                summary_data = (
                    monthly_summary.get("summary", {})
                    if isinstance(monthly_summary, dict)
                    else {}
                )
                if summary_data:
                    cols = st.columns(4)
                    with cols[0]:
                        st.metric(
                            t("metric_forecast_success_rate"),
                            f"{float(summary_data.get('forecast_success_rate', 0.0)):.2%}",
                        )
                    with cols[1]:
                        st.metric(
                            t("metric_rolling_success_rate"),
                            f"{float(summary_data.get('rolling_success_rate', 0.0)):.2%}",
                        )
                    with cols[2]:
                        st.metric(
                            t("metric_latest_month_accuracy"),
                            f"{float(summary_data.get('latest_month_accuracy', 0.0)):.2%}",
                        )
                    with cols[3]:
                        st.metric(
                            t("metric_forecast_direction"),
                            str(summary_data.get("forecast_direction", "NEUTRAL")),
                        )

                    if summary_data.get("start_month") and summary_data.get(
                        "end_month"
                    ):
                        st.caption(
                            f"{t('coverage')}: {summary_data.get('start_month')} -> {summary_data.get('end_month')} | "
                            f"{t('signal_count')}: {summary_data.get('total_signals', 0)}"
                        )
                    if lang == "zh":
                        direction = str(
                            summary_data.get("forecast_direction", "NEUTRAL")
                        )
                        dir_map = {
                            "BULLISH": "下一月参考方向：**偏多**（近期看多信号占上风）",
                            "BEARISH": "下一月参考方向：**偏空**（近期看空信号占上风）",
                            "NEUTRAL": "下一月参考方向：**中性**（多空信号接近，暂无明显倾向）",
                        }
                        st.info(
                            dir_map.get(
                                direction,
                                f"下一月参考方向：{direction}",
                            )
                        )
                        acc = float(summary_data.get("latest_month_accuracy", 0))
                        st.markdown(
                            f"**最新月准确率 {acc:.1%}**：表示该月信号与次日涨跌方向一致的比例。"
                            f"滚动成功率 **{float(summary_data.get('rolling_success_rate', 0)):.1%}** "
                            f"反映近 {summary_data.get('months_trained', train_months)} 个月的整体稳定性。"
                        )
                    else:
                        st.info(
                            f"Forecast direction: **{summary_data.get('forecast_direction', 'NEUTRAL')}** "
                            f"(research signal only, not trading advice)."
                        )

                monthly_df = monthly_df.copy()
                if not monthly_df.empty:
                    monthly_df["accuracy"] = pd.to_numeric(
                        monthly_df.get("accuracy", 0), errors="coerce"
                    ).fillna(0.0)
                    monthly_df["avg_return"] = pd.to_numeric(
                        monthly_df.get("avg_return", 0), errors="coerce"
                    ).fillna(0.0)
                    monthly_df["signals"] = pd.to_numeric(
                        monthly_df.get("signals", 0), errors="coerce"
                    ).fillna(0.0)
                    monthly_df["win_rate"] = pd.to_numeric(
                        monthly_df.get("win_rate", 0), errors="coerce"
                    ).fillna(0.0)

                    monthly_melted = monthly_df[["month", "accuracy", "win_rate"]].melt(
                        id_vars=["month"],
                        value_vars=["accuracy", "win_rate"],
                        var_name="metric",
                        value_name="value",
                    )
                    monthly_melted["metric"] = monthly_melted["metric"].astype(str)
                    monthly_melted["value"] = pd.to_numeric(
                        monthly_melted["value"], errors="coerce"
                    ).fillna(0.0)

                    monthly_line = (
                        alt.Chart(monthly_melted)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X("month:N", title=t("month")),
                            y=alt.Y("value:Q", title=t("rate")),
                            color=alt.Color(
                                "metric:N",
                                scale=alt.Scale(range=_DASH_COLORS[:2]),
                                title=t("metric_forecast_direction"),
                            ),
                            tooltip=["month", "metric", "value"],
                        )
                        .properties(title=t("monthly_metrics_title"), height=260)
                    )
                    st.altair_chart(
                        _configure_chart(monthly_line), use_container_width=True
                    )

                    monthly_bar = (
                        alt.Chart(monthly_df)
                        .mark_bar(cornerRadiusEnd=4)
                        .encode(
                            x=alt.X("month:N", title=t("month")),
                            y=alt.Y("signals:Q", title=t("signal_count")),
                            color=alt.Color(
                                "accuracy:Q",
                                scale=alt.Scale(
                                    range=["#CCFBF1", "#0D9488", "#115E59"]
                                ),
                                title=t("eval_accuracy"),
                            ),
                            tooltip=[
                                "month",
                                "signals",
                                "accuracy",
                                "avg_return",
                                "win_rate",
                            ],
                        )
                        .properties(title=t("monthly_metrics_title"), height=250)
                    )
                    st.altair_chart(
                        _configure_chart(monthly_bar), use_container_width=True
                    )

                    monthly_display = monthly_df[
                        [
                            "month",
                            "signals",
                            "correct_signals",
                            "accuracy",
                            "avg_return",
                            "win_rate",
                            "avg_confidence",
                        ]
                    ].rename(
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
                        hide_index=True,
                    )


if __name__ == "__main__":
    main()
