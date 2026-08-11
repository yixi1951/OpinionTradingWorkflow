from __future__ import annotations

import glob
import html
import json
import os
from pathlib import Path
from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from opinion_trading.core.env_bootstrap import load_dotenv_if_present

load_dotenv_if_present(Path(__file__).resolve().parents[2])

from opinion_trading.core.evaluation import (  # noqa: E402
    evaluate_signals,
    load_prices,
    normalize_price_frame,
)
from opinion_trading.core.monthly_training import (  # noqa: E402
    build_monthly_training_frame,
    fetch_prices_with_timeout,
    load_latest_monthly_training,
    load_training_history,
    save_monthly_training_report,
)

from opinion_trading.core.openclaw_adapter import OpenClawClient  # noqa: E402
from opinion_trading.core.ai_sentiment import sentiment_intensity_label  # noqa: E402
from opinion_trading.ui_helpers import (  # noqa: E402
    build_openclaw_activity_feed,
    build_openclaw_summary,
    build_pick_contribution,
    build_pick_narrative,
    build_picks_detail_table,
    build_sentiment_engine_stats,
    compute_raw_capture_rates,
    build_symbol_sentiment_summary,
    evidence_stats,
    infer_score_source,
    label_platform_column,
    monthly_methodology_text,
    parse_platform_scores,
    platform_label,
    prepare_customer_raw,
    symbol_display,
    top_comment_rows,
)
from opinion_trading.core.user_workspace import UserWorkspace  # noqa: E402
from opinion_trading.ui.mvp_pages import (  # noqa: E402
    render_alerts_tab,
    render_ai_pipeline_tab,
    render_disclaimer_banner,
    render_review_tab,
    render_user_login_sidebar,
    render_watchlist_tab,
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
        "show_more_comments": "Show {n} more",
        "show_less_comments": "Show less",
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
        "ui_theme_label": "Theme",
        "ui_theme_light": "Light",
        "ui_theme_dark": "Dark",
        "openclaw_engine_title": "OpenClaw Engine",
        "openclaw_connected": "Connected",
        "openclaw_disconnected": "Not connected (keyword fallback)",
        "openclaw_probe_btn": "Test connection",
        "openclaw_status_title": "OpenClaw Engine",
        "openclaw_probe_hint": "First probe may take 30-60s (DeepSeek).",
        "openclaw_score_stats": "AI-scored rows in latest raw CSV: {ai}/{total}",
        "openclaw_score_metric": "AI-scored rows",
        "openclaw_no_raw": "No raw CSV loaded yet.",
        "status_last_report": "Latest report",
        "status_running_hint": "Realtime job may still be running — refresh to update.",
        "rank_label": "Rank",
        "refresh_data": "Refresh data",
        "sidebar_paths": "Data paths",
        "hero_tagline": "OpenClaw monitors sentiment in real time · DeepSeek scoring · AI stock picks",
        "hero_kpi_picks": "Realtime picks",
        "hero_kpi_alerts": "Score alerts",
        "hero_kpi_platforms": "Platforms",
        "hero_kpi_report": "Last report",
        "hero_kpi_fallback": "Low-quality share",
        "hero_kpi_none": "—",
        "hero_top_picks": "Today's top picks",
        "hero_no_picks": "No picks yet — run a daily or realtime refresh.",
        "data_clean_fmt": "Showing {kept} clean posts (filtered {dropped} low-quality).",
        "data_status_fmt": "{picks} picks · {posts} posts · {platforms} platforms · {sent} sentiment points",
        "wf_export_csv": "Download walk-forward folds (CSV)",
        "user_guide_title": "What you can do here",
        "user_guide_body": """
1. **Realtime Picks** — OpenClaw aggregates multi-platform sentiment into Top 3 rankings and reason cards.
2. **OpenClaw Live** — See the AI pipeline, analysis feed, and which texts were scored by OpenClaw vs keyword fallback.
3. **Sentiment** — Platform trends and contribution weights.
4. **Evidence** — User comments + reference texts that support each pick.

Connect OpenClaw via `OPENCLAW_URL` (see `scripts/run_demo_openclaw.ps1`). Sidebar shows live connection status.
""",
        "tab_openclaw": "OpenClaw Live",
        "openclaw_url_label": "Endpoint",
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
        "openclaw_setup_expander": "Setup / error details",
        "reference_expand_hint": "News & analysis (lower weight) — click to expand",
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
        "hero_kpi_ai_coverage": "AI scored",
        "hero_kpi_sentiment_bias": "Bull / Bear",
        "sentiment_engine_title": "AI sentiment engine",
        "sentiment_engine_body": "OpenClaw scores social posts from -1 (bearish) to +1 (bullish). Low-quality spam is filtered before you see results.",
        "filter_controls": "Filter controls",
        "min_samples_platform": "Min samples per platform",
        "include_zero_scores": "Include zero scores (treat 0 as valid)",
        "filter_hint_samples": "Higher sample thresholds hide thin lines.",
        "signal_stats": "Signal stats",
        "show_platform_counts": "Show platform sample counts",
        "signal_stats_hint": "Counts are based on valid sentiment rows.",
        "export_section": "Export",
        "export_hint": "CSV reflects current filters.",
        "download_csv": "Download CSV",
        "no_platforms_after_filter": "No platforms remain after filtering; lower Min samples.",
        "platform_sample_counts": "Platform sample counts",
        "actions": "Actions",
        "contrib_actions_hint": "Contribution table and chart update instantly.",
        "chip_trend": "Trend",
        "chip_multisource": "Multi-source",
        "chip_drivers": "Drivers",
        "chip_weights": "Weights",
        "chip_snapshot": "Snapshot",
        "chip_ranked": "Ranked bars",
        "chip_ai_engine": "AI engine",
        "symbol_sentiment_card": "Symbol sentiment snapshot",
        "symbol_avg_score": "Avg sentiment",
        "symbol_comment_count": "Valid comments",
        "platform_breakdown": "By platform",
        "quote_positive": "Top bullish quote",
        "quote_negative": "Top bearish quote",
        "deploy_aliyun_title": "Alibaba Cloud realtime scoring",
        "deploy_aliyun_hint": "Set OPENCLAW_URL on the server to your sentiment proxy; run realtime via systemd or cron.",
        "tab_analyst": "Analyst Scores",
        "analyst_compare_title": "Multi-Agent Score Comparison",
        "analyst_compare_body": "Compare scores from Sentiment, Technical, and Fundamental analysts per symbol. The consensus score fuses all three with configurable weights.",
        "analyst_select_symbol": "Select symbol for analyst breakdown",
        "analyst_no_data": "No multi-agent signal data available. Run the pipeline with `analysis.enabled: true` in settings.yaml first.",
        "analyst_score_chart_title": "Analyst Score Breakdown per Symbol",
        "analyst_consensus_title": "Consensus Signal Detail",
        "analyst_col_analyst": "Analyst",
        "analyst_col_score": "Score",
        "analyst_col_confidence": "Confidence",
        "analyst_col_reasoning": "Reasoning",
        "analyst_kelly": "Kelly Fraction",
        "analyst_direction": "Direction",
        "analyst_n_analysts": "Analysts",
        "analyst_n_agreeing": "Agreeing",
        "analyst_backtest_hint": "Run `python main.py --mode backtest --multi-agent` to generate comparison data.",
        "analyst_sentiment": "Sentiment",
        "analyst_technical": "Technical",
        "analyst_fundamental": "Fundamental",
        "analyst_backtest_title": "Sentiment vs Multi-Agent: Backtest Comparison",
        "analyst_backtest_load": "Load comparison data",
        "analyst_backtest_no_data": "No comparison CSV found. Run `--mode backtest --multi-agent` first.",
        "analyst_backtest_csv": "Comparison CSV path",
        "analyst_backtest_default_path": "data/reports/backtest_comparison.csv",
        "quality_gate_title": "Raw data quality gate",
        "quality_gate_pass": "PASS — signals allowed",
        "quality_gate_fail": "FAIL / blocked — confidence reduced",
        "quality_gate_no_data": "No quality gate record. Run daily mode first.",
        "quality_gate_multiplier": "Conf. multiplier",
        "quality_gate_noise": "Noise rate",
        "quality_gate_fallback": "Fallback rate",
        "quality_gate_history_title": "Quality gate history",
        "quality_gate_history_hint": "Dashed line = quality.max_fallback_rate ({threshold}).",
        "quality_metric_fallback": "Fallback %",
        "quality_metric_noise": "Noise %",
        "quality_chart_date": "Trade date",
        "signal_explanation_title": "Decision explanation",
        "paper_price_hint": "Paper trades use market close (yfinance/akshare) when available.",
        "walk_forward_title": "Walk-forward (out-of-sample)",
        "walk_forward_run": "Run walk-forward in UI",
        "walk_forward_load_report": "Load saved report",
        "walk_forward_no_report": "No walk_forward_report.md — run below or `python main.py --mode walk_forward`.",
        "walk_forward_avg_test_acc": "Avg test accuracy",
        "walk_forward_avg_degradation": "Train→test accuracy gap",
        "walk_forward_avg_deg": "Train→test acc gap",
        "walk_forward_folds_table": "Walk-forward folds (out-of-sample)",
        "wf_col_train": "Train window",
        "wf_col_test": "Test window",
        "wf_col_train_acc": "Train acc",
        "wf_col_test_acc": "Test acc",
        "wf_col_train_sharpe": "Train Sharpe",
        "wf_col_test_sharpe": "Test Sharpe",
        "wf_col_deg": "Acc gap",
        "wf_col_test_n": "Test signals",
        "walk_forward_recommendation": "Recommendation",
        "paper_account_title": "Paper account",
        "paper_equity_title": "Paper equity curve",
        "paper_equity_hint": "From trade_history.jsonl; marks-to-market via latest close when available.",
        "paper_cash": "Cash",
        "paper_positions": "Positions",
        "paper_total_value": "Total value",
        "paper_last_trades": "Recent paper fills",
        "paper_no_state": "No state.json — run daily mode first.",
        "event_log_title": "Audit trail (signals vs fills)",
        "event_log_empty": "No events yet — run daily after upgrade.",
        "event_log_filter": "Filter by event type",
        "event_log_all_types": "All types",
        "export_zip": "Download reports bundle (ZIP)",
        "export_zip_hint": "Includes recent picks, summaries, signals, paper state, event log.",
        "collect_progress_title": "Latest parallel crawl log",
        "collect_progress_file": "File",
        "collect_progress_empty": "No progress lines yet.",
        "auth_title": "Dashboard access",
        "auth_prompt": "Enter access password",
        "auth_wrong": "Incorrect password.",
        "auth_env_hint": "Set STREAMLIT_DASHBOARD_PASSWORD to enable.",
        "settings_preview_title": "Strategy settings (read-only)",
        "settings_preview_hint": "From config/settings.yaml — edit file and restart pipeline to apply.",
        "universe_edit_title": "Stock universe (write settings.yaml)",
        "universe_edit_label": "One symbol per line (e.g. 600519.SH)",
        "universe_save": "Save universe to settings.yaml",
        "universe_saved": "Saved. Re-run daily/realtime to use new symbols.",
        "explanation_lang_hint": "Pipeline explanations: set project.explanation_lang to en in settings.yaml",
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
        "platform_radar": "平台雷达（情绪对比）",
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
        "show_more_comments": "展示更多 ({n} 条)",
        "show_less_comments": "收起",
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
        "tab_openclaw": "OpenClaw 实时",
        "ui_theme_label": "界面主题",
        "ui_theme_light": "浅色",
        "ui_theme_dark": "深色",
        "openclaw_engine_title": "OpenClaw 分析引擎",
        "openclaw_connected": "已连接",
        "openclaw_disconnected": "未连接（当前为关键词兜底）",
        "openclaw_probe_btn": "测试连接",
        "openclaw_url_label": "服务地址",
        "openclaw_probe_hint": "首次探测约需 30-60 秒（DeepSeek）。",
        "openclaw_score_stats": "最新 raw CSV 中 AI 打分：{ai}/{total} 条",
        "openclaw_score_metric": "AI 打分条数",
        "openclaw_no_raw": "尚未加载 raw CSV。",
        "status_last_report": "最新报告",
        "status_running_hint": "选股任务可能仍在运行，点击刷新查看最新结果。",
        "rank_label": "排名",
        "refresh_data": "刷新数据",
        "sidebar_paths": "数据路径",
        "hero_tagline": "OpenClaw 实时监测舆情 · DeepSeek 情感分析 · AI 智能选股",
        "hero_kpi_picks": "实时选股",
        "hero_kpi_alerts": "评分告警",
        "hero_kpi_platforms": "监测平台",
        "hero_kpi_report": "更新时间",
        "hero_kpi_fallback": "低质占比",
        "hero_kpi_none": "—",
        "hero_top_picks": "今日推荐",
        "hero_no_picks": "暂无推荐，请先刷新日批或实时选股。",
        "data_clean_fmt": "已展示 {kept} 条有效帖文（已过滤 {dropped} 条低质/灌水）。",
        "data_status_fmt": "推荐 {picks} 只 · 有效帖 {posts} 条 · 平台 {platforms} 个 · 舆情点 {sent} 条",
        "wf_export_csv": "下载 walk-forward 折表 (CSV)",
        "user_guide_title": "你可以这样使用本页",
        "user_guide_body": """
1. **实时选股** — OpenClaw 汇总多平台情感分，输出 Top 3 排名与选股原因卡。
2. **OpenClaw 实时** — 查看 AI 分析流水线、逐条分析流水，以及 OpenClaw / 关键词 打分来源。
3. **舆情分析** — 各平台趋势与贡献权重。
4. **评论依据** — 用户观点 + 参考文本，支撑选股结论。

连接 OpenClaw：设置 `OPENCLAW_URL` 或运行 `scripts/run_demo_openclaw.ps1`；侧边栏显示连接状态。
""",
        "openclaw_status_title": "OpenClaw 分析引擎",
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
        "openclaw_setup_expander": "连接说明 / 错误详情",
        "reference_expand_hint": "参考文本（新闻/分析，权重较低）— 点击展开",
        "reference_comments": "参考文本（新闻 / 分析，权重较低）",
        "badge_openclaw": "OpenClaw AI",
        "badge_keyword": "关键词",
        "badge_user_comment": "用户观点",
        "badge_news": "新闻",
        "badge_reference": "参考",
        "no_platform_scores": "暂无平台分数明细",
        "guide_trend_title": "图表说明：情感趋势",
        "guide_trend_body": "每条折线代表一个平台的**月度平均情绪分**（-1 偏空 ~ +1 偏多）。上行=情绪改善，下行=情绪恶化。可通过「最少样本数」过滤样本过少的平台。",
        "guide_contrib_title": "图表说明：平台贡献（选股解释）",
        "guide_contrib_body": "分数来自**最近一轮实时选股**的各平台分项；权重来自 config/settings.yaml。**加权贡献 = 分数 × 平台权重**，**贡献 %** 越高表示该平台对本次排名影响越大。",
        "guide_snapshot_title": "平台情绪快照",
        "guide_snapshot_body": "展示所选股票在各平台的**最新情绪分**。绿色偏多、红色偏空、灰色中性/无信号，便于快速对比强弱平台。",
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
        "hero_kpi_ai_coverage": "AI 已评分",
        "hero_kpi_sentiment_bias": "多空倾向",
        "sentiment_engine_title": "AI 情感分析引擎",
        "sentiment_engine_body": "OpenClaw 将社交媒体帖文评为 -1（偏空）到 +1（偏多）。展示前会自动过滤灌水、广告等低质内容。",
        "filter_controls": "筛选条件",
        "min_samples_platform": "每平台最少样本数",
        "include_zero_scores": "包含零分（将 0 视为有效信号）",
        "filter_hint_samples": "提高样本阈值可隐藏样本过少的折线。",
        "signal_stats": "信号统计",
        "show_platform_counts": "显示各平台样本数",
        "signal_stats_hint": "样本数基于有效情感记录统计。",
        "export_section": "导出",
        "export_hint": "CSV 与当前筛选条件一致。",
        "download_csv": "下载 CSV",
        "no_platforms_after_filter": "筛选后无剩余平台，请降低最少样本数。",
        "platform_sample_counts": "各平台样本数",
        "actions": "操作",
        "contrib_actions_hint": "贡献表与图表随选择即时更新。",
        "chip_trend": "趋势",
        "chip_multisource": "多源",
        "chip_drivers": "驱动",
        "chip_weights": "权重",
        "chip_snapshot": "快照",
        "chip_ranked": "排序柱",
        "chip_ai_engine": "AI 引擎",
        "symbol_sentiment_card": "单股情感快照",
        "symbol_avg_score": "平均情感分",
        "symbol_comment_count": "有效评论",
        "platform_breakdown": "分平台均值",
        "quote_positive": "最强看多摘录",
        "quote_negative": "最强看空摘录",
        "deploy_aliyun_title": "阿里云实时打分",
        "deploy_aliyun_hint": "在服务器配置 OPENCLAW_URL 指向情感代理，并用 systemd/cron 跑 realtime 任务。",
        "tab_analyst": "分析师评分",
        "analyst_compare_title": "多 Agent 评分对比",
        "analyst_compare_body": "对比情绪、技术、基本面三位分析师对每只股票的评分。共识分按配置权重融合三者得出。",
        "analyst_select_symbol": "选择股票代码查看分析师评分明细",
        "analyst_no_data": "暂无多 Agent 信号数据。请先在 settings.yaml 中启用 `analysis.enabled: true` 并运行 pipeline。",
        "analyst_score_chart_title": "各股票分析师评分拆解",
        "analyst_consensus_title": "共识信号详情",
        "analyst_col_analyst": "分析师",
        "analyst_col_score": "评分",
        "analyst_col_confidence": "置信度",
        "analyst_col_reasoning": "分析依据",
        "analyst_kelly": "凯利仓位",
        "analyst_direction": "方向",
        "analyst_n_analysts": "分析师数",
        "analyst_n_agreeing": "一致数",
        "analyst_backtest_hint": "运行 `python main.py --mode backtest --multi-agent` 生成对比数据。",
        "analyst_sentiment": "情绪",
        "analyst_technical": "技术",
        "analyst_fundamental": "基本面",
        "analyst_backtest_title": "纯情绪 vs 多 Agent：回测对比",
        "analyst_backtest_load": "加载对比数据",
        "analyst_backtest_no_data": "未找到对比 CSV。请先运行 `--mode backtest --multi-agent`。",
        "analyst_backtest_csv": "对比 CSV 路径",
        "analyst_backtest_default_path": "data/reports/backtest_comparison.csv",
        "quality_gate_title": "原始数据质量门控",
        "quality_gate_pass": "通过 — 可发信号",
        "quality_gate_fail": "未通过 / 已阻断 — 置信度已下调",
        "quality_gate_no_data": "暂无质量门控记录，请先运行 daily 模式。",
        "quality_gate_multiplier": "置信度系数",
        "quality_gate_noise": "噪声率",
        "quality_gate_fallback": "Fallback 率",
        "quality_gate_history_title": "质量门控历史",
        "quality_gate_history_hint": "虚线 = quality.max_fallback_rate（{threshold}）。",
        "quality_metric_fallback": "Fallback %",
        "quality_metric_noise": "噪声 %",
        "quality_chart_date": "交易日",
        "signal_explanation_title": "决策说明",
        "paper_price_hint": "纸面成交优先使用当日收盘价（yfinance / akshare），缺失时回退合成价。",
        "walk_forward_title": "Walk-forward 样本外评估",
        "walk_forward_run": "在界面运行 walk-forward",
        "walk_forward_load_report": "加载已保存报告",
        "walk_forward_no_report": "尚无 walk_forward_report.md — 点击下方运行或执行 `python main.py --mode walk_forward`。",
        "walk_forward_avg_test_acc": "平均测试准确率",
        "walk_forward_avg_degradation": "训练→测试准确率落差",
        "walk_forward_avg_deg": "训练→测试准确率落差",
        "walk_forward_folds_table": "Walk-forward 各折明细",
        "wf_col_train": "训练窗口",
        "wf_col_test": "测试窗口",
        "wf_col_train_acc": "训练准确率",
        "wf_col_test_acc": "测试准确率",
        "wf_col_train_sharpe": "训练 Sharpe",
        "wf_col_test_sharpe": "测试 Sharpe",
        "wf_col_deg": "准确率落差",
        "wf_col_test_n": "测试信号数",
        "walk_forward_recommendation": "结论建议",
        "paper_account_title": "纸面账户",
        "paper_equity_title": "纸面净值曲线",
        "paper_equity_hint": "由 trade_history.jsonl 重建；持仓按最近收盘价市值（若可获取）。",
        "paper_cash": "现金",
        "paper_positions": "持仓",
        "paper_total_value": "总市值",
        "paper_last_trades": "最近纸面成交",
        "paper_no_state": "尚无 state.json — 请先运行 daily 模式。",
        "event_log_title": "审计流水（信号 vs 成交）",
        "event_log_empty": "暂无事件 — 升级后运行 daily 会写入 event_log.jsonl。",
        "event_log_filter": "按事件类型筛选",
        "event_log_all_types": "全部类型",
        "export_zip": "下载报告打包 (ZIP)",
        "export_zip_hint": "含近期选股、日报、信号、纸面状态与审计流水。",
        "collect_progress_title": "最近并行采集日志",
        "collect_progress_file": "文件",
        "collect_progress_empty": "暂无进度记录。",
        "auth_title": "仪表盘访问",
        "auth_prompt": "请输入访问密码",
        "auth_wrong": "密码错误。",
        "auth_env_hint": "设置环境变量 STREAMLIT_DASHBOARD_PASSWORD 后启用。",
        "settings_preview_title": "策略配置（只读）",
        "settings_preview_hint": "来自 config/settings.yaml — 修改后需重跑 daily/realtime。",
        "universe_edit_title": "股票池（写入 settings.yaml）",
        "universe_edit_label": "每行一个代码（如 600519.SH）",
        "universe_save": "保存股票池到 settings.yaml",
        "universe_saved": "已保存，请重跑 daily/realtime。",
        "explanation_lang_hint": "流水线说明语言：在 settings.yaml 设置 project.explanation_lang: en",
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
    """Return a fresh OpenClawClient; drop stale session objects after code reload."""
    client = st.session_state.get("_openclaw_client")
    # Hot-reload can leave an old instance without health_check / probe signature.
    if client is None or not callable(getattr(client, "health_check", None)):
        st.session_state["_openclaw_client"] = OpenClawClient()
    return st.session_state["_openclaw_client"]


def _openclaw_probe(force: bool = False, *, llm: bool = False) -> Dict[str, object]:
    """UI status probe. Default = fast /health (no LLM). Set llm=True for full score test."""
    client = _openclaw_client()
    if not client.is_configured():
        return {
            "connected": False,
            "url": None,
            "message": "OPENCLAW_URL not set",
            "mode": "health",
        }
    cache_key = "_openclaw_probe_llm" if llm else "_openclaw_probe_health"
    if not force and cache_key in st.session_state:
        return st.session_state[cache_key]
    if llm:
        # Cap LLM probe for interactive button use
        os.environ.setdefault("OPENCLAW_PROBE_TIMEOUT", "45")
        result = client.probe()
    else:
        health_fn = getattr(client, "health_check", None)
        if callable(health_fn):
            result = health_fn(timeout=2.0)
        else:
            # Very old adapter: avoid blocking LLM probe on first paint
            result = {
                "connected": bool(client.base_url),
                "url": client.base_url,
                "message": "health_check unavailable; restart Streamlit to reload adapter",
                "mode": "health",
            }
    st.session_state[cache_key] = result
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
    # UI must not block first paint on a 120s LLM probe
    os.environ.setdefault("OPENCLAW_PROBE_TIMEOUT", "45")


def _render_openclaw_sidebar() -> None:
    probe = _openclaw_probe(llm=False)
    connected = bool(probe.get("connected"))
    status_text = t("openclaw_connected") if connected else t("openclaw_disconnected")
    css = "openclaw-on" if connected else "openclaw-off"
    st.markdown(
        f"""
        <div class='openclaw-status-card'>
            <div class='openclaw-status-meta'>OpenClaw · {t('openclaw_engine_title')}</div>
            <span class='status-pill {css} status-pill--dashboard'>
                <span class='status-dot' aria-hidden='true'></span>
                <span>{status_text}</span>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if probe.get("url"):
        st.caption("分析服务已连接" if connected else "分析服务未连接")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("刷新状态", use_container_width=True, key="oc_health_btn"):
            st.session_state.pop("_openclaw_probe_health", None)
            _openclaw_probe(force=True, llm=False)
            st.rerun()
    with col_b:
        if st.button(t("openclaw_probe_btn"), use_container_width=True, key="oc_probe_btn"):
            st.session_state.pop("_openclaw_probe_llm", None)
            with st.spinner("DeepSeek 打分探测中…"):
                _openclaw_probe(force=True, llm=True)
            st.rerun()
    if not connected:
        with st.expander(t("openclaw_setup_expander"), expanded=False):
            st.caption(t("openclaw_not_connected_hint"))
            if probe.get("message"):
                st.code(str(probe.get("message", ""))[:220])


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
    probe = _openclaw_probe(llm=False)
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


# Dashboard design tokens — warm-neutral soft-futurism palette
_DASH_ACCENT = "#8B7355"
_DASH_COLORS = [
    "#8B7355",
    "#3D6B4F",
    "#A89070",
    "#6E6760",
    "#A24B45",
    "#8A827A",
    "#C4A882",
    "#5C534A",
]
_SENTIMENT_BAR_SCALE = alt.Scale(
    domain=["bull", "bear", "flat"],
    range=["#3D6B4F", "#A24B45", "#8A827A"],
)


def _sentiment_color(score: float) -> str:
    if score > 0.05:
        return "#3D6B4F"
    if score < -0.05:
        return "#A24B45"
    return "#8A827A"


def _platform_chip_html(platform: str, score: float, *, suffix: str = "") -> str:
    label = _platform_label(platform)
    text = f"{label} {score:+.3f}{suffix}" if suffix else f"{label} {score:+.3f}"
    color = _sentiment_color(score)
    return (
        f"<span class='platform-chip' style='color:{color};'>"
        f"<span class='platform-chip-label'>{text}</span></span>"
    )


def _configure_chart(chart: alt.Chart) -> alt.Chart:
    from opinion_trading.ui.dashboard_styles import chart_theme_colors

    theme = "light"
    try:
        theme = str(st.session_state.get("ui_theme", "light"))
    except Exception:
        pass
    colors = chart_theme_colors(theme)
    font = colors["font"]
    return (
        chart.configure_axis(
            labelFont=font,
            titleFont=font,
            labelColor=colors["muted"],
            titleColor=colors["ink"],
            gridColor=colors["grid"],
            domainColor=colors["grid"],
            tickColor=colors["grid"],
        )
        .configure_view(strokeWidth=0, fill=colors["view_fill"])
        .configure_title(
            font=font,
            fontSize=14,
            fontWeight=500,
            color=colors["ink"],
        )
        .configure_legend(
            labelFont=font,
            titleFont=font,
            labelColor=colors["muted"],
            titleColor=colors["ink"],
            symbolType="circle",
            orient="top",
            padding=8,
        )
    )


def _inject_dashboard_styles(theme: str = "light") -> None:
    from opinion_trading.ui.dashboard_styles import inject_dashboard_styles

    inject_dashboard_styles(theme)


def _sync_theme_from_query() -> None:
    """Restore theme from ?theme=light|dark when present."""
    try:
        qp = st.query_params
        raw = qp.get("theme", None)
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if raw in ("light", "dark"):
            st.session_state["ui_theme"] = raw
    except Exception:
        pass


def _persist_theme_query(theme: str) -> None:
    try:
        st.query_params["theme"] = theme
    except Exception:
        pass


def _latest_file(pattern: str) -> str:
    files = sorted(glob.glob(pattern))
    return files[-1] if files else ""


@st.cache_data(ttl=60, show_spinner=False)
def _load_latest_realtime_picks_cached(report_dir: str) -> pd.DataFrame:
    path = _latest_file(str(Path(report_dir) / "realtime_picks_*.csv"))
    if not path:
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["_source_path"] = path
    return df


def _picks_from_sentiment(sentiment_df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Build a picks-like table from sentiment history when realtime CSV is thin/stale."""
    if sentiment_df is None or sentiment_df.empty:
        return pd.DataFrame()
    view = sentiment_df.copy()
    view["sentiment_score"] = pd.to_numeric(view.get("sentiment_score"), errors="coerce")
    view["trade_date"] = pd.to_datetime(view.get("trade_date"), errors="coerce")
    view = view.dropna(subset=["symbol", "sentiment_score"])
    if view.empty:
        return pd.DataFrame()
    # Prefer latest trade_date window (wider — thin history often spans months)
    latest = view["trade_date"].max()
    if pd.notna(latest):
        window = view[view["trade_date"] >= (latest - pd.Timedelta(days=120))]
        if not window.empty:
            view = window
    grouped = (
        view.groupby("symbol", as_index=False)
        .agg(
            avg_score=("sentiment_score", "mean"),
            platforms=("platform", lambda s: ", ".join(sorted({str(x) for x in s if str(x)}))),
            samples=("sentiment_score", "size"),
        )
        .sort_values("avg_score", ascending=False)
        .head(int(top_n))
    )
    grouped["platform_scores"] = grouped["platforms"]
    grouped["_source_path"] = "derived:sentiment_history"
    return grouped.reset_index(drop=True)


def _picks_from_raw(raw_df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Aggregate symbol scores from merged raw posts (ai_score preferred)."""
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()
    view = raw_df.copy()
    score_col = None
    for cand in ("ai_score", "sentiment_score", "score"):
        if cand in view.columns:
            score_col = cand
            break
    if score_col is None:
        return pd.DataFrame()
    view[score_col] = pd.to_numeric(view[score_col], errors="coerce")
    view = view.dropna(subset=["symbol", score_col])
    if view.empty:
        return pd.DataFrame()
    plat = (
        view.groupby(["symbol", "platform"], as_index=False)[score_col]
        .mean()
        if "platform" in view.columns
        else view.groupby(["symbol"], as_index=False)[score_col].mean()
    )
    rows = []
    if "platform" in plat.columns:
        for symbol, g in plat.groupby("symbol"):
            ps = ", ".join(
                f"{r.platform}:{float(getattr(r, score_col)):.3f}"
                for _, r in g.sort_values("platform").iterrows()
            )
            rows.append(
                {
                    "symbol": symbol,
                    "avg_score": round(float(g[score_col].mean()), 4),
                    "platform_scores": ps,
                    "samples": int(len(view[view["symbol"] == symbol])),
                }
            )
    else:
        for _, r in plat.iterrows():
            rows.append(
                {
                    "symbol": r["symbol"],
                    "avg_score": round(float(r[score_col]), 4),
                    "platform_scores": "",
                    "samples": int(len(view[view["symbol"] == r["symbol"]])),
                }
            )
    if not rows:
        return pd.DataFrame()
    out = (
        pd.DataFrame(rows)
        .sort_values("avg_score", ascending=False)
        .head(int(top_n))
        .reset_index(drop=True)
    )
    out["_source_path"] = "derived:raw_posts"
    return out


def _load_latest_realtime_picks(report_dir: str) -> pd.DataFrame:
    candidates = [
        report_dir,
        "data/reports",
        "data/reports_landing",
    ]
    best = pd.DataFrame()
    best_mtime = -1.0
    for d in candidates:
        if not d or not Path(d).exists():
            continue
        df = _load_latest_realtime_picks_cached(d)
        if df.empty:
            continue
        src = ""
        if "_source_path" in df.columns and len(df):
            src = str(df["_source_path"].iloc[0])
        mtime = Path(src).stat().st_mtime if src and Path(src).exists() else 0.0
        if mtime >= best_mtime:
            best = df
            best_mtime = mtime
    return best


@st.cache_data(ttl=60, show_spinner=False)
def _load_latest_alerts_cached(report_dir: str) -> pd.DataFrame:
    path = _latest_file(str(Path(report_dir) / "realtime_alerts_*.jsonl"))
    if not path:
        return pd.DataFrame()
    return pd.read_json(path, lines=True)


def _load_latest_alerts(report_dir: str) -> pd.DataFrame:
    for d in (report_dir, "data/reports", "data/reports_landing"):
        if not d or not Path(d).exists():
            continue
        df = _load_latest_alerts_cached(d)
        if not df.empty:
            return df
    return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def _load_raw_posts_merged_cached(raw_dir: str, max_files: int = 12) -> pd.DataFrame:
    """Merge recent raw_posts_*.csv — latest-only misses older dense crawls."""
    root = Path(raw_dir)
    if not root.exists():
        return pd.DataFrame()
    files = sorted(root.glob("raw_posts_*.csv"), key=lambda p: p.name)
    if not files:
        return pd.DataFrame()
    files = files[-max(1, int(max_files)) :]
    frames: List[pd.DataFrame] = []
    for path in files:
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty:
            continue
        df["_source_file"] = path.name
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    # Prefer newest file when the same post URL appears twice
    if "url" in out.columns:
        out = out.drop_duplicates(subset=["url"], keep="last")
    elif {"symbol", "platform", "text"}.issubset(out.columns):
        out = out.drop_duplicates(
            subset=["symbol", "platform", "text"], keep="last"
        )
    out["_source_path"] = f"merged:{raw_dir}:{len(files)}files"
    return out


def _load_latest_raw_posts(raw_dir: str) -> pd.DataFrame:
    best = pd.DataFrame()
    best_n = -1
    for d in (raw_dir, "data/raw"):
        if not d or not Path(d).exists():
            continue
        df = _load_raw_posts_merged_cached(d)
        if len(df) > best_n:
            best = df
            best_n = len(df)
    return best


@st.cache_data(ttl=60, show_spinner=False)
def _load_sentiment_history_cached(path: str) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame()
    return pd.read_json(path, lines=True)


def _load_sentiment_history(path: str) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for p in (
        path,
        "data/memory/sentiment_history.jsonl",
        "data/memory_landing/sentiment_history.jsonl",
    ):
        if not p:
            continue
        df = _load_sentiment_history_cached(p)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    if "trade_date" in out.columns and "symbol" in out.columns and "platform" in out.columns:
        out = out.drop_duplicates(
            subset=["trade_date", "symbol", "platform"], keep="last"
        )
    return out


def _data_freshness_caption(
    picks_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    sentiment_df: pd.DataFrame,
    *,
    clean_stats: Dict[str, int] | None = None,
) -> str:
    n_plat_raw = (
        int(raw_df["platform"].nunique())
        if raw_df is not None and not raw_df.empty and "platform" in raw_df.columns
        else 0
    )
    plat = (
        int(sentiment_df["platform"].nunique())
        if sentiment_df is not None and not sentiment_df.empty and "platform" in sentiment_df.columns
        else 0
    )
    base = t("data_status_fmt").format(
        picks=len(picks_df) if picks_df is not None else 0,
        posts=len(raw_df) if raw_df is not None else 0,
        platforms=plat or n_plat_raw,
        sent=len(sentiment_df) if sentiment_df is not None else 0,
    )
    if clean_stats and int(clean_stats.get("dropped_total", 0) or 0) > 0:
        base += " · " + t("data_clean_fmt").format(
            kept=int(clean_stats.get("kept", 0) or 0),
            dropped=int(clean_stats.get("dropped_total", 0) or 0),
        )
    return base


def _hero_picks_html(picks_df: pd.DataFrame) -> str:
    if picks_df is None or picks_df.empty or "avg_score" not in picks_df.columns:
        return f"<div class='hero-pick-empty'>{t('hero_no_picks')}</div>"
    view = picks_df.copy()
    view["avg_score"] = pd.to_numeric(view["avg_score"], errors="coerce").fillna(0.0)
    view = view.sort_values("avg_score", ascending=False).head(3)
    rows = []
    for i, (_, row) in enumerate(view.iterrows(), start=1):
        symbol = str(row.get("symbol", ""))
        score = float(row.get("avg_score", 0.0))
        tone = "pos" if score > 0.05 else "neg" if score < -0.05 else "neu"
        rows.append(
            "<div class='hero-pick-row'>"
            f"<span class='hero-pick-rank'>#{i}</span>"
            f"<span class='hero-pick-sym'>{html.escape(_symbol_label(symbol))}</span>"
            f"<span class='hero-pick-score {tone}'>{score:+.3f}</span>"
            "</div>"
        )
    return (
        f"<div class='hero-picks-title'>{t('hero_top_picks')}</div>"
        f"<div class='hero-picks-list'>{''.join(rows)}</div>"
    )


def _render_dashboard_hero(
    picks_count: int,
    alerts_count: int,
    platform_count: int,
    report_dir: str,
    *,
    picks_df: pd.DataFrame | None = None,
    engine_stats: Dict[str, object] | None = None,
    capture_rates: Dict[str, float] | None = None,
    clean_stats: Dict[str, int] | None = None,
) -> None:
    _, report_time = _latest_report_meta(report_dir)
    report_display = report_time or t("hero_kpi_none")
    stats = engine_stats or {}
    cap = capture_rates or {}
    ai_pct = stats.get("openclaw_pct", 0.0)
    bull = stats.get("bullish_pct", 0.0)
    bear = stats.get("bearish_pct", 0.0)
    bias_label = f"+{bull:.0f}% / -{bear:.0f}%"
    # Prefer explicit clean drop rate over engineer "fallback" jargon
    if clean_stats and int(clean_stats.get("input", 0) or 0) > 0:
        dropped = int(clean_stats.get("dropped_total", 0) or 0)
        total = int(clean_stats.get("input", 0) or 0)
        fb_display = f"{(dropped / total) * 100:.0f}%"
        fb_warn = (dropped / total) > 0.35
    else:
        fb_rate = float(cap.get("fallback_rate", 0.0) or 0.0)
        fb_display = f"{fb_rate * 100:.0f}%" if cap.get("total_rows", 0) else "—"
        fb_warn = bool(cap.get("total_rows", 0) and fb_rate > 0.35)
    fb_value_cls = (
        "hero-kpi-value mono hero-kpi-value--warn" if fb_warn else "hero-kpi-value mono"
    )
    picks_html = _hero_picks_html(picks_df if picks_df is not None else pd.DataFrame())
    st.markdown(
        f"""
        <div class="dashboard-hero dashboard-hero--terminal">
            <div class="hero-top">
                <div class="hero-copy">
                    <div class="dashboard-kicker">OpenClaw</div>
                    <div class="dashboard-title">{t('header_title')}</div>
                    <div class="dashboard-subtitle">{t('hero_tagline')}</div>
                    <div class="hero-picks-panel">{picks_html}</div>
                </div>
                <div class="hero-kpi-grid hero-kpi-grid--4">
                    <div class="hero-kpi">
                        <div class="hero-kpi-label">{t('hero_kpi_picks')}</div>
                        <div class="hero-kpi-value mono">{picks_count}</div>
                    </div>
                    <div class="hero-kpi">
                        <div class="hero-kpi-label">{t('hero_kpi_platforms')}</div>
                        <div class="hero-kpi-value mono">{platform_count}</div>
                    </div>
                    <div class="hero-kpi">
                        <div class="hero-kpi-label">{t('hero_kpi_ai_coverage')}</div>
                        <div class="hero-kpi-value mono">{ai_pct}%</div>
                    </div>
                    <div class="hero-kpi">
                        <div class="hero-kpi-label">{t('hero_kpi_sentiment_bias')}</div>
                        <div class="hero-kpi-value small mono">{bias_label}</div>
                    </div>
                    <div class="hero-kpi">
                        <div class="hero-kpi-label">{t('hero_kpi_fallback')}</div>
                        <div class="{fb_value_cls}">{fb_display}</div>
                    </div>
                    <div class="hero-kpi">
                        <div class="hero-kpi-label">{t('hero_kpi_report')}</div>
                        <div class="hero-kpi-value small">{report_display}</div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sentiment_engine_strip(
    engine_stats: Dict[str, object],
    *,
    capture_rates: Dict[str, float] | None = None,
    clean_stats: Dict[str, int] | None = None,
) -> None:
    usable = int(engine_stats.get("usable_rows", 0) or 0)
    oc = int(engine_stats.get("openclaw_rows", 0) or 0)
    avg = float(engine_stats.get("avg_ai_score", 0.0) or 0.0)
    tone = sentiment_intensity_label(avg, _ui_lang())
    dropped = int((clean_stats or {}).get("dropped_total", 0) or 0)
    zh = _ui_lang() == "zh"
    metrics = [
        ( "有效帖文" if zh else "Clean posts", usable),
        ( "AI 评分" if zh else "AI scored", oc),
        ( "平均情感" if zh else "Avg sentiment", f"{avg:+.2f}"),
        ( "整体倾向" if zh else "Tone", tone),
    ]
    if dropped:
        metrics.append(("已过滤" if zh else "Filtered", dropped))
    metrics_html = "".join(
        f"<span class='engine-metric'><span class='engine-metric-label'>{html.escape(str(k))}</span>"
        f"{html.escape(str(v))}</span>"
        for k, v in metrics
    )
    st.markdown(
        f"""
        <div class="panel-card panel-card--accent sentiment-engine-strip">
            <div class="section-kicker">{t('chip_ai_engine')}</div>
            <div class="sentiment-engine-title">{t('sentiment_engine_title')}</div>
            <p class="sentiment-engine-body">{t('sentiment_engine_body')}</p>
            <div class="sentiment-engine-metrics">
                {metrics_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
            f"<span class='status-pill {oc_cls}'>"
            f"<span class='status-dot' aria-hidden='true'></span>"
            f"OpenClaw · {oc_label}</span>"
        )
    if report_time:
        pills.append(
            f"<span class='status-pill live'>"
            f"<span class='status-dot' aria-hidden='true'></span>"
            f"{t('status_last_report')}: {report_time}</span>"
        )
    pills.append(
        f"<span class='status-pill'>"
        f"<span class='status-dot' aria-hidden='true'></span>"
        f"{t('realtime_picks')}: {picks_count}</span>"
    )
    pills.append(
        f"<span class='status-pill'>"
        f"<span class='status-dot' aria-hidden='true'></span>"
        f"{t('score_alerts')}: {alerts_count}</span>"
    )
    pills.append(
        f"<span class='status-pill'>"
        f"<span class='status-dot' aria-hidden='true'></span>"
        f"{t('platform_label')}: {platform_count}</span>"
    )
    st.markdown(
        f"<div class='panel-card panel-card--compact'><div class='status-strip'>{''.join(pills)}</div></div>",
        unsafe_allow_html=True,
    )


def _render_pick_leaderboard(picks_df: pd.DataFrame) -> None:
    if picks_df.empty:
        st.info(t("no_realtime_picks"))
        return

    view = picks_df.copy()
    drop_cols = [c for c in ("_source_path", "_source_file") if c in view.columns]
    if drop_cols:
        view = view.drop(columns=drop_cols)
    if "avg_score" not in view.columns:
        st.dataframe(view, use_container_width=True)
        return

    view["avg_score"] = pd.to_numeric(view["avg_score"], errors="coerce").fillna(0.0)
    view = view.sort_values("avg_score", ascending=False).reset_index(drop=True)
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown(f"#### {t('realtime_picks')}")
    st.markdown("<div class='section-kicker'>Top 5</div>", unsafe_allow_html=True)
    cols = st.columns(min(5, len(view)))

    for idx, row in view.head(5).iterrows():
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
                f"<span style='color:#8A827A;font-size:0.8125rem;'>"
                f"{t('no_platform_scores')}</span>"
            )

        with cols[idx]:
            rank_cls = f"rank-{min(idx + 1, 3)}"
            st.markdown(
                f"""
                <div class="pick-card {rank_cls}">
                    <div class="pick-rank">{t('rank_label')} #{idx + 1}</div>
                    <div class="pick-symbol">{_symbol_label(symbol)}</div>
                    <div style="display:flex;align-items:baseline;gap:0.65rem;flex-wrap:wrap;">
                        <div class="pick-score {score_class}">{score:+.4f}</div>
                        <span class="trend-pill {score_class}">{score:+.2f}</span>
                    </div>
                    <div style="margin-top:0.45rem;">{_score_badge(score)}</div>
                    <div style="margin-top:0.65rem;">{platform_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander(t("key_fields"), expanded=False):
        st.caption(t("key_fields_help"))
        detail = build_picks_detail_table(view, _ui_lang())
        st.dataframe(detail, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _trend_arrow(score: float) -> str:
    if score >= 0.15:
        return "<span class='trend-up'>▲</span>"
    if score <= -0.15:
        return "<span class='trend-down'>▼</span>"
    return "<span class='trend-flat'>■</span>"


def _comment_preview_label(platform: str, score: float, text: str, max_len: int = 40) -> str:
    preview = text if len(text) <= max_len else f"{text[:max_len]}…"
    return f"{_platform_label(platform)} · {score:+.2f} · {preview}"


def _render_symbol_sentiment_card(raw_df: pd.DataFrame, symbol: str) -> None:
    summary = build_symbol_sentiment_summary(raw_df, symbol, lang=_ui_lang())
    avg = float(summary.get("avg_score", 0.0) or 0.0)
    tone = sentiment_intensity_label(avg, _ui_lang())
    score_class = "pos" if avg > 0.05 else "neg" if avg < -0.05 else "neu"
    count = int(summary.get("comment_count", 0) or 0)
    plat_rows = summary.get("platforms") or []
    plat_html = ""
    if plat_rows:
        chips = []
        for item in plat_rows[:6]:
            pscore = float(item.get("score", 0.0))
            chips.append(_platform_chip_html(str(item.get("platform", "")), pscore))
        plat_html = "".join(chips)
    else:
        plat_html = (
            f"<span style='color:var(--dash-subtle);font-size:0.8125rem;'>"
            f"{t('no_valid_comments')}</span>"
        )
    pos_q = str(summary.get("top_positive") or "").strip()
    neg_q = str(summary.get("top_negative") or "").strip()
    quote_block = ""
    if pos_q:
        quote_block += (
            f"<div class='symbol-quote symbol-quote--pos'>"
            f"<span class='symbol-quote-label'>{t('quote_positive')}</span>"
            f"{pos_q}</div>"
        )
    if neg_q:
        quote_block += (
            f"<div class='symbol-quote symbol-quote--neg'>"
            f"<span class='symbol-quote-label'>{t('quote_negative')}</span>"
            f"{neg_q}</div>"
        )
    st.markdown(
        f"""
        <div class="panel-card symbol-sentiment-card">
            <div class="section-kicker">{t('symbol_sentiment_card')}</div>
            <div class="symbol-sentiment-head">
                <div class="symbol-sentiment-title">{_symbol_label(symbol)}</div>
                <div class="pick-score {score_class} mono">{avg:+.4f}</div>
            </div>
            <div class="symbol-sentiment-meta">
                <span class="trend-pill {score_class}">{tone}</span>
                <span class="engine-metric">
                    <span class="engine-metric-label">{t('symbol_comment_count')}</span>
                    {count}
                </span>
            </div>
            <div class="symbol-sentiment-platforms">{plat_html}</div>
            {quote_block}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_comment_highlights(
    comments_df: pd.DataFrame,
    *,
    key_prefix: str,
    empty_message: str | None = None,
    use_expanders: bool = True,
    initial_visible: int = 4,
) -> None:
    if comments_df.empty:
        if empty_message:
            st.caption(empty_message)
        return

    total = len(comments_df)
    show_all_key = f"{key_prefix}_show_all"
    if show_all_key not in st.session_state:
        st.session_state[show_all_key] = False
    show_all = bool(st.session_state[show_all_key])
    limit = max(1, initial_visible)
    visible_df = comments_df if show_all or total <= limit else comments_df.head(limit)

    if use_expanders:
        st.caption(t("click_to_expand"))
    for idx, (_, row) in enumerate(visible_df.iterrows()):
        platform = str(row.get("platform", "") or "")
        score = float(row.get("ai_score", 0) or 0)
        full_text = str(row.get("full_text") or row.get("display_text") or "")
        if not full_text:
            continue
        label = _comment_preview_label(platform, score, full_text)
        if use_expanders:
            with st.expander(f"{label} · #{idx + 1}", expanded=False):
                st.markdown(_comment_badges_html(row), unsafe_allow_html=True)
                st.markdown(full_text)
                post_time = str(row.get("post_time", "") or "").strip()
                if post_time:
                    st.caption(f"{t('col_post_time')}: {post_time}")
                url = str(row.get("url", "") or "")
                if url.startswith("http"):
                    st.markdown(f"[{t('col_url')}]({url})")
        else:
            st.markdown(
                f"<div class='ref-snippet'>"
                f"<div class='ref-snippet-head'>{label}</div>"
                f"{_comment_badges_html(row)}"
                f"<div class='ref-snippet-body'>{full_text}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            post_time = str(row.get("post_time", "") or "").strip()
            if post_time:
                st.caption(f"{t('col_post_time')}: {post_time}")
            url = str(row.get("url", "") or "")
            if url.startswith("http"):
                st.markdown(f"[{t('col_url')}]({url})")

    if total > limit:
        remaining = total - limit
        if not show_all:
            if st.button(
                t("show_more_comments").format(n=remaining),
                key=f"{key_prefix}_more",
                use_container_width=True,
            ):
                st.session_state[show_all_key] = True
                st.rerun()
        elif st.button(
            t("show_less_comments"),
            key=f"{key_prefix}_less",
            use_container_width=True,
        ):
            st.session_state[show_all_key] = False
            st.rerun()


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
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown(f"##### #{rank} {_symbol_label(symbol)}")
        st.markdown(build_pick_narrative(symbol, avg_score, contrib, raw_df, lang=lang))

        stats = evidence_stats(raw_df, symbol)
        st.caption(_evidence_caption(stats))
        if stats["valid"] < 5:
            st.warning(t("sample_low_warning"))
        if stats["valid"] < 3:
            st.info(t("comments_few_hint"))

        top_rows = top_comment_rows(
            raw_df, symbol, top_n=8, include_reference=True, ref_n=3
        )
        pos_items = top_rows["positive"]
        neg_items = top_rows["negative"]
        ref_items = top_rows["reference"]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f"<div class='comment-panel'><div class='comment-panel-title'>"
                f"{t('positive_highlight')} ({len(pos_items)})</div>",
                unsafe_allow_html=True,
            )
            _render_comment_highlights(
                pos_items,
                key_prefix=f"pick_pos_{symbol}",
                empty_message=t("no_valid_comments"),
            )
            st.markdown("</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(
                f"<div class='comment-panel'><div class='comment-panel-title'>"
                f"{t('negative_highlight')} ({len(neg_items)})</div>",
                unsafe_allow_html=True,
            )
            _render_comment_highlights(
                neg_items,
                key_prefix=f"pick_neg_{symbol}",
                empty_message=t("no_valid_comments"),
            )
            st.markdown("</div>", unsafe_allow_html=True)
        if not ref_items.empty:
            with st.expander(
                f"{t('reference_expand_hint')} ({len(ref_items)})",
                expanded=False,
            ):
                _render_comment_highlights(
                    ref_items,
                    key_prefix=f"pick_ref_{symbol}",
                    empty_message=None,
                    use_expanders=False,
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
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)


def _render_analyst_tab(memory_dir: str, report_dir: str) -> None:
    """Render the multi-agent analyst score comparison tab."""
    _render_quality_gate_panel(_load_latest_quality_gate(memory_dir))
    st.caption(t("paper_price_hint"))
    _render_info_box(t("analyst_compare_title"), t("analyst_compare_body"))
    st.caption(t("analyst_backtest_hint"))

    # ── Load signal history and extract multi-agent data ──
    signal_path = Path(memory_dir) / "signal_history.jsonl"
    multi_agent_rows: List[Dict] = []
    all_signals: List[Dict] = []

    if signal_path.exists():
        for line in signal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                all_signals.append(row)
                # Check for multi-agent fields
                scores = row.get("analyst_scores")
                has_scores = bool(scores) and (
                    isinstance(scores, dict) or (isinstance(scores, str) and scores.strip())
                )
                if has_scores or row.get("consensus_score") is not None:
                    multi_agent_rows.append(row)
            except json.JSONDecodeError:
                continue

    has_multi_agent = len(multi_agent_rows) > 0

    # ── Section 1: Per-symbol analyst breakdown ──
    st.markdown(f"#### {t('analyst_score_chart_title')}")
    if has_multi_agent:
        symbols = sorted(set(r.get("symbol", "") for r in multi_agent_rows if r.get("symbol")))
        selected = st.selectbox(t("analyst_select_symbol"), symbols, key="analyst_symbol")

        # Filter for selected symbol
        symbol_rows = [r for r in multi_agent_rows if r.get("symbol") == selected]
        if symbol_rows:
            latest = symbol_rows[-1]  # most recent
            _render_analyst_detail_card(latest, selected)

            # Bar chart: analyst scores over time
            _render_analyst_timeline(symbol_rows, selected)
    else:
        # Fallback: try to build a live view from any consensus data in recent signals
        consensus_inferred = _try_infer_consensus(all_signals, memory_dir)
        if consensus_inferred:
            symbols = sorted(set(r.get("symbol", "") for r in consensus_inferred if r.get("symbol")))
            selected = st.selectbox(t("analyst_select_symbol"), symbols, key="analyst_symbol_infer")
            latest_rows = [r for r in consensus_inferred if r.get("symbol") == selected]
            if latest_rows:
                _render_analyst_detail_card(latest_rows[-1], selected)
                _render_analyst_timeline(latest_rows, selected)
        else:
            st.info(t("analyst_no_data"))

    # ── Section 2: Backtest comparison ──
    st.markdown("---")
    st.markdown(f"#### {t('analyst_backtest_title')}")
    cmp_path = st.text_input(
        t("analyst_backtest_csv"),
        value=t("analyst_backtest_default_path"),
        key="analyst_cmp_path",
    )
    if st.button(t("analyst_backtest_load"), key="analyst_load_cmp"):
        _render_backtest_comparison(cmp_path)


def _render_analyst_detail_card(latest_row: Dict, symbol: str) -> None:
    """Render a detail card for the latest consensus signal."""
    analyst_scores_raw = latest_row.get("analyst_scores") or "{}"
    analyst_confidences_raw = latest_row.get("analyst_confidences") or "{}"

    try:
        analyst_scores = json.loads(analyst_scores_raw) if isinstance(analyst_scores_raw, str) else analyst_scores_raw
    except (json.JSONDecodeError, TypeError):
        analyst_scores = {}
    try:
        analyst_confidences = json.loads(analyst_confidences_raw) if isinstance(analyst_confidences_raw, str) else analyst_confidences_raw
    except (json.JSONDecodeError, TypeError):
        analyst_confidences = {}

    consensus_score = float(latest_row.get("consensus_score", latest_row.get("score", 0.0)))
    confidence = float(latest_row.get("confidence", 0.0))
    direction = str(latest_row.get("consensus_direction", latest_row.get("action", "NEUTRAL")))
    kelly = float(latest_row.get("kelly_fraction", 0.0))
    n_analysts = int(latest_row.get("n_analysts", 0))
    n_agreeing = int(latest_row.get("n_agreeing", 0))

    score_class = "pos" if consensus_score > 0.05 else "neg" if consensus_score < -0.05 else "neu"

    st.markdown(
        f"""
        <div class="panel-card">
            <div class="section-kicker">{t('analyst_consensus_title')}</div>
            <div class="symbol-sentiment-head">
                <div class="symbol-sentiment-title">{_symbol_label(symbol)}</div>
                <div class="pick-score {score_class} mono">{consensus_score:+.4f}</div>
            </div>
            <div class="symbol-sentiment-meta">
                <span class="trend-pill {score_class}">{direction}</span>
                <span class="engine-metric">
                    <span class="engine-metric-label">{t('analyst_col_confidence')}</span>
                    {confidence:.2%}
                </span>
                <span class="engine-metric">
                    <span class="engine-metric-label">{t('analyst_kelly')}</span>
                    {kelly:.2%}
                </span>
                <span class="engine-metric">
                    <span class="engine-metric-label">{t('analyst_n_analysts')}</span>
                    {n_analysts}
                </span>
                <span class="engine-metric">
                    <span class="engine-metric-label">{t('analyst_n_agreeing')}</span>
                    {n_agreeing}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Analyst breakdown table
    analyst_map = {
        "sentiment": t("analyst_sentiment"),
        "technical": t("analyst_technical"),
        "fundamental": t("analyst_fundamental"),
    }
    breakdown_rows = []
    for aname, alabel in analyst_map.items():
        ascore = analyst_scores.get(aname)
        aconf = analyst_confidences.get(aname)
        if ascore is not None:
            breakdown_rows.append({
                t("analyst_col_analyst"): alabel,
                t("analyst_col_score"): f"{float(ascore):+.4f}",
                t("analyst_col_confidence"): f"{float(aconf or 0):.2%}",
            })

    if breakdown_rows:
        st.dataframe(pd.DataFrame(breakdown_rows), use_container_width=True, hide_index=True)

        # Mini bar chart for analyst scores
        chart_data = pd.DataFrame(breakdown_rows)
        chart_data["score_val"] = pd.to_numeric(
            chart_data[t("analyst_col_score")].str.replace("+", ""), errors="coerce"
        ).fillna(0.0)
        bar = (
            alt.Chart(chart_data)
            .mark_bar(cornerRadiusEnd=12)
            .encode(
                x=alt.X("score_val:Q", title=t("analyst_col_score")),
                y=alt.Y(t("analyst_col_analyst") + ":N", sort="-x", title=None),
                color=alt.Color(
                    "score_val:Q",
                    scale=alt.Scale(range=_DASH_COLORS),
                    title=t("analyst_col_score"),
                ),
                tooltip=[t("analyst_col_analyst"), t("analyst_col_score"), t("analyst_col_confidence")],
            )
            .properties(height=140)
        )
        st.altair_chart(_configure_chart(bar), use_container_width=True)

    explanation = (
        str(latest_row.get("explanation") or "").strip()
        or str(latest_row.get("reason") or "").strip()
    )
    if explanation:
        from opinion_trading.core.explainability import translate_signal_explanation_for_ui

        lang = st.session_state.get("lang", "zh")
        explanation = translate_signal_explanation_for_ui(
            explanation, lang, row=latest_row
        )
        st.markdown(f"**{t('signal_explanation_title')}**")
        st.markdown(
            f"<div class='guide-card' style='white-space:pre-wrap;'>{html.escape(explanation)}</div>",
            unsafe_allow_html=True,
        )


def _render_analyst_timeline(rows: List[Dict], symbol: str) -> None:
    """Render a timeline of analyst scores over time."""
    if len(rows) < 2:
        return

    records = []
    for r in rows:
        td = r.get("trade_date", "")
        try:
            analyst_scores_raw = r.get("analyst_scores") or "{}"
            if isinstance(analyst_scores_raw, str):
                scores = json.loads(analyst_scores_raw)
            else:
                scores = analyst_scores_raw
        except (json.JSONDecodeError, TypeError):
            scores = {}
        cs = float(r.get("consensus_score", r.get("score", 0.0)))
        records.append({
            "trade_date": str(td)[:10] if td else "",
            "sentiment": float(scores.get("sentiment", 0)),
            "technical": float(scores.get("technical", 0)),
            "fundamental": float(scores.get("fundamental", 0)),
            "consensus": cs,
        })

    if not records:
        return

    df = pd.DataFrame(records)
    df = df.dropna(subset=["trade_date"])
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df = df.sort_values("trade_date")

    melted = df.melt(
        id_vars=["trade_date"],
        value_vars=["sentiment", "technical", "fundamental", "consensus"],
        var_name="analyst",
        value_name="score",
    )
    analyst_labels = {
        "sentiment": t("analyst_sentiment"),
        "technical": t("analyst_technical"),
        "fundamental": t("analyst_fundamental"),
        "consensus": "Consensus",
    }
    melted["analyst_label"] = melted["analyst"].map(analyst_labels).fillna(melted["analyst"])

    line = (
        alt.Chart(melted)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("trade_date:T", title=t("month")),
            y=alt.Y("score:Q", title=t("analyst_col_score")),
            color=alt.Color(
                "analyst_label:N",
                scale=alt.Scale(range=_DASH_COLORS),
                title=t("analyst_col_analyst"),
            ),
            tooltip=["trade_date", "analyst_label", "score"],
        )
        .properties(title=f"{symbol} — {t('analyst_score_chart_title')}", height=260)
    )
    st.altair_chart(_configure_chart(line), use_container_width=True)


def _try_infer_consensus(all_signals: List[Dict], memory_dir: str) -> List[Dict]:
    """Try to build multi-agent-like entries from enriched signal history."""
    # Check if we have consensus-like fields in signal data
    enriched = []
    for row in all_signals:
        has_extra = any(k in row for k in ("consensus_score", "analyst_scores", "kelly_fraction"))
        if has_extra:
            enriched.append(row)
    return enriched


def _render_backtest_comparison(cmp_path: str) -> None:
    """Load and display the backtest comparison CSV."""
    path = Path(cmp_path)
    if not path.exists():
        st.warning(t("analyst_backtest_no_data"))
        return

    try:
        df = pd.read_csv(path)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Highlight the better value in each metric
        for _, row in df.iterrows():
            metric = str(row.get("Metric", ""))
            sent_val = str(row.get("Sentiment Only", "0%"))
            ma_val = str(row.get("Multi-Agent", "0%"))
            st.markdown(
                f"- **{metric}**: Sentiment {sent_val} | Multi-Agent {ma_val}"
            )
    except Exception as e:
        st.error(f"Failed to load comparison: {e}")


def _load_latest_quality_gate(memory_dir: str) -> Dict:
    path = Path(memory_dir) / "quality_gate_history.jsonl"
    if not path.exists():
        return {}
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {}


def _render_quality_gate_panel(gate: Dict) -> None:
    if not gate:
        st.caption(t("quality_gate_no_data"))
        return
    passed = bool(gate.get("overall_pass", True))
    mult = float(gate.get("sentiment_confidence_multiplier", 1.0) or 1.0)
    blocked = bool(gate.get("block_new_signals", False))
    noise = float(gate.get("noise_rate", 0.0) or 0.0)
    fb = float(gate.get("fallback_rate", 0.0) or 0.0)
    pill_cls = "openclaw-on" if passed and not blocked else "openclaw-off"
    status = t("quality_gate_pass") if passed and not blocked else t("quality_gate_fail")
    st.markdown(
        f"""
        <div class="panel-card panel-card--compact">
            <div class="section-kicker">{t('quality_gate_title')}</div>
            <span class="status-pill {pill_cls} status-pill--dashboard">
                <span class="status-dot" aria-hidden="true"></span>
                <span>{status}</span>
            </span>
            <div class="symbol-sentiment-meta" style="margin-top:0.65rem;">
                <span class="engine-metric">
                    <span class="engine-metric-label">{t('quality_gate_multiplier')}</span>
                    {mult:.2f}
                </span>
                <span class="engine-metric">
                    <span class="engine-metric-label">{t('quality_gate_noise')}</span>
                    {noise:.1%}
                </span>
                <span class="engine-metric">
                    <span class="engine-metric-label">{t('quality_gate_fallback')}</span>
                    {fb:.1%}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    msgs = gate.get("messages") or []
    if msgs:
        for m in msgs[:6]:
            st.caption(str(m))


def _load_paper_state(memory_dir: str) -> Dict:
    path = Path(memory_dir) / "state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_recent_trades(memory_dir: str, limit: int = 8) -> pd.DataFrame:
    path = Path(memory_dir) / "trade_history.jsonl"
    if not path.exists():
        return pd.DataFrame()
    rows: List[Dict] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit * 3 :]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return pd.DataFrame(rows[-limit:] if rows else [])


def _render_paper_account_panel(
    memory_dir: str,
    today_aggregated: Dict | None = None,
) -> None:
    state = _load_paper_state(memory_dir)
    if not state:
        st.info(t("paper_no_state"))
        return
    cash = float(state.get("cash", 0))
    positions = state.get("positions") or {}
    open_pos = {k: int(v) for k, v in positions.items() if int(v) > 0}
    total_val: float | None = None
    try:
        from opinion_trading.skills.trade_simulation import PaperTradingSkill

        skill = PaperTradingSkill(100_000.0, 0.2, use_market_prices=False)
        total_val = skill.portfolio_value(today_aggregated or {}, state)
    except Exception:
        total_val = None
    st.markdown(f"#### {t('paper_account_title')}")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(t("paper_cash"), f"{cash:,.2f}")
    with c2:
        st.metric(t("paper_positions"), len(open_pos))
    with c3:
        tv = f"{total_val:,.2f}" if total_val is not None else "—"
        st.metric(t("paper_total_value"), tv)
    st.caption(t("paper_price_hint"))
    if open_pos:
        st.markdown(f"**{t('paper_positions')}**")
        st.json(open_pos)
    trades_df = _load_recent_trades(memory_dir)
    if not trades_df.empty:
        st.markdown(f"**{t('paper_last_trades')}**")
        st.dataframe(trades_df, use_container_width=True, hide_index=True)
    _render_paper_equity_chart(memory_dir)


def _render_paper_equity_chart(memory_dir: str) -> None:
    from opinion_trading.core.paper_equity import build_paper_equity_curve

    eq = build_paper_equity_curve(memory_dir)
    if eq.empty:
        return
    st.markdown(f"#### {t('paper_equity_title')}")
    st.caption(t("paper_equity_hint"))
    chart = (
        alt.Chart(eq)
        .mark_line(color=_DASH_ACCENT, point=True)
        .encode(
            x=alt.X("trade_date:T", title=""),
            y=alt.Y("total_value:Q", title=""),
            tooltip=[
                alt.Tooltip("trade_date:T"),
                alt.Tooltip("total_value:Q", format=",.2f"),
                alt.Tooltip("cash:Q", format=",.2f"),
                alt.Tooltip("drawdown_pct:Q", format=".2%"),
            ],
        )
        .properties(height=220)
    )
    st.altair_chart(_configure_chart(chart), use_container_width=True)


def _render_quality_gate_history_chart(memory_dir: str) -> None:
    from opinion_trading.core.quality_gate_history import load_quality_gate_history

    rows = load_quality_gate_history(memory_dir, limit=40)
    if not rows:
        return
    st.markdown(f"#### {t('quality_gate_history_title')}")
    df = pd.DataFrame(rows)
    if "trade_date" not in df.columns:
        return
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df = df.dropna(subset=["trade_date"]).sort_values("trade_date")
    if df.empty:
        return
    try:
        from opinion_trading.core.config_loader import load_runtime_config

        thr = 0.35
        q = load_runtime_config("config/settings.yaml").quality
        if q:
            thr = float(q.max_fallback_rate)
    except Exception:
        thr = 0.35
    df["fallback_pct"] = pd.to_numeric(df["fallback_rate"], errors="coerce").fillna(0) * 100
    df["noise_pct"] = pd.to_numeric(df["noise_rate"], errors="coerce").fillna(0) * 100
    long = df.melt(
        id_vars=["trade_date"],
        value_vars=["fallback_pct", "noise_pct"],
        var_name="metric",
        value_name="pct",
    )
    long["metric"] = long["metric"].map(
        {
            "fallback_pct": t("quality_metric_fallback"),
            "noise_pct": t("quality_metric_noise"),
        }
    )
    chart = (
        alt.Chart(long)
        .mark_line(point=True)
        .encode(
            x=alt.X("trade_date:T", title=t("quality_chart_date")),
            y=alt.Y("pct:Q", title="%"),
            color=alt.Color("metric:N", title=None),
            tooltip=["trade_date:T", "metric:N", alt.Tooltip("pct:Q", format=".1f")],
        )
        .properties(height=200)
    )
    rule = (
        alt.Chart(pd.DataFrame({"y": [thr * 100]}))
        .mark_rule(color="#A24B45", strokeDash=[4, 4])
        .encode(y="y:Q")
    )
    st.altair_chart(_configure_chart(chart + rule), use_container_width=True)
    st.caption(t("quality_gate_history_hint").format(threshold=f"{thr:.0%}"))


def _render_walk_forward_folds_table(report_dir: str) -> None:
    from opinion_trading.core.walk_forward_cache import load_walk_forward_json

    data = load_walk_forward_json(report_dir)
    if not data or not data.get("folds"):
        return
    st.markdown(f"**{t('walk_forward_folds_table')}**")
    rows = []
    for f in data["folds"]:
        rows.append(
            {
                t("wf_col_train"): f"{f['train_start']} ~ {f['train_end']}",
                t("wf_col_test"): f"{f['test_start']} ~ {f['test_end']}",
                t("wf_col_train_acc"): f"{float(f['train_accuracy']):.2%}",
                t("wf_col_test_acc"): f"{float(f['test_accuracy']):.2%}",
                t("wf_col_train_sharpe"): f"{float(f['train_sharpe']):.4f}",
                t("wf_col_test_sharpe"): f"{float(f['test_sharpe']):.4f}",
                t("wf_col_deg"): f"{float(f['degradation_accuracy']):+.2%}",
                t("wf_col_test_n"): int(f.get("test_signals", 0)),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        f"{t('walk_forward_avg_test_acc')}: {float(data.get('avg_test_accuracy', 0)):.2%} | "
        f"{t('walk_forward_avg_deg')}: {float(data.get('avg_degradation_accuracy', 0)):+.2%}"
    )
    from opinion_trading.core.walk_forward_cache import export_walk_forward_folds_csv

    csv_bytes = export_walk_forward_folds_csv(report_dir)
    if len(csv_bytes) > 80:
        st.download_button(
            t("wf_export_csv"),
            data=csv_bytes,
            file_name="walk_forward_folds.csv",
            mime="text/csv",
            key="wf_export_csv_btn",
        )


def _render_walk_forward_panel(
    memory_dir: str,
    report_dir: str,
    price_df: pd.DataFrame | None,
    *,
    auto_run: bool = True,
) -> None:
    st.markdown(f"#### {t('walk_forward_title')}")
    report_path = Path(report_dir) / "walk_forward_report.md"
    signal_path = str(Path(memory_dir) / "signal_history.jsonl")
    can_run = (
        price_df is not None
        and not price_df.empty
        and Path(signal_path).exists()
    )
    cache_key = f"wf_auto_{report_dir}_{memory_dir}"
    if auto_run and can_run and not st.session_state.get(cache_key):
        from opinion_trading.core.walk_forward import (
            run_walk_forward,
            save_walk_forward_report,
        )

        try:
            report = run_walk_forward(signal_path, price_df, n_folds=3)
            save_walk_forward_report(report_dir, report)
            st.session_state[cache_key] = True
            st.session_state["wf_last_recommendation"] = report.recommendation
        except Exception as exc:
            st.caption(f"walk-forward auto: {exc}")

    rec = st.session_state.get("wf_last_recommendation")
    if not rec and report_path.exists():
        from opinion_trading.core.walk_forward_cache import load_walk_forward_json

        cached = load_walk_forward_json(report_dir)
        if cached:
            rec = cached.get("recommendation")

    _render_walk_forward_folds_table(report_dir)

    if rec:
        st.info(rec)
    elif report_path.exists():
        st.markdown(report_path.read_text(encoding="utf-8")[:2500])
    else:
        st.caption(t("walk_forward_no_report"))
    if not can_run:
        if price_df is None or price_df.empty:
            st.caption(t("upload_required"))
        return
    if st.button(t("walk_forward_run"), key="wf_run_ui"):
        from opinion_trading.core.walk_forward import (
            run_walk_forward,
            save_walk_forward_report,
        )

        report = run_walk_forward(signal_path, price_df, n_folds=3)
        save_walk_forward_report(report_dir, report)
        st.session_state["wf_last_recommendation"] = report.recommendation
        st.session_state[cache_key] = True
        st.success(t("walk_forward_load_report"))
        st.rerun()


def _require_dashboard_auth() -> None:
    expected = os.environ.get("STREAMLIT_DASHBOARD_PASSWORD", "").strip()
    if not expected:
        return
    if st.session_state.get("dashboard_authenticated"):
        return
    st.markdown(f"### {t('auth_title')}")
    st.caption(t("auth_env_hint"))
    pwd = st.text_input(t("auth_prompt"), type="password", key="dashboard_pwd")
    if st.button("OK", key="dashboard_auth_btn"):
        if pwd == expected:
            st.session_state["dashboard_authenticated"] = True
            st.rerun()
        else:
            st.error(t("auth_wrong"))
    st.stop()


def _render_collect_progress_expander(report_dir: str) -> None:
    rep = Path(report_dir)
    if not rep.is_dir():
        return
    logs = sorted(rep.glob("collect_progress_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        return
    latest = logs[0]
    with st.expander(t("collect_progress_title"), expanded=False):
        st.caption(f"{t('collect_progress_file')}: `{latest.name}`")
        lines = latest.read_text(encoding="utf-8").strip().splitlines()
        tail = lines[-12:] if len(lines) > 12 else lines
        rows = []
        for ln in tail:
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption(t("collect_progress_empty"))


def _render_export_zip_button(report_dir: str, memory_dir: str, raw_dir: str) -> None:
    """Build ZIP only when clicked — avoid packing data on every Streamlit rerun."""
    if st.button(t("export_zip"), use_container_width=True, help=t("export_zip_hint"), key="export_zip_btn"):
        from opinion_trading.core.export_bundle import build_dashboard_export_zip

        try:
            with st.spinner("打包中…"):
                payload = build_dashboard_export_zip(report_dir, memory_dir, raw_dir)
            st.session_state["_export_zip_bytes"] = payload
            st.success(f"已生成 ZIP（{len(payload):,} bytes）")
        except Exception as exc:
            st.caption(f"ZIP: {exc}")
            return
    payload = st.session_state.get("_export_zip_bytes")
    if isinstance(payload, (bytes, bytearray)) and payload:
        st.download_button(
            label="下载 export.zip",
            data=payload,
            file_name="openclaw_export.zip",
            mime="application/zip",
            use_container_width=True,
            key="export_zip_download",
        )


def _render_event_log_panel(memory_dir: str) -> None:
    from opinion_trading.core.event_log import load_recent_events

    with st.expander(t("event_log_title"), expanded=False):
        events = load_recent_events(memory_dir, limit=80)
        if not events:
            st.caption(t("event_log_empty"))
            return
        types = sorted({str(e.get("event_type", "")) for e in events if e.get("event_type")})
        choice = st.selectbox(
            t("event_log_filter"),
            [t("event_log_all_types")] + types,
            key="event_log_type_filter",
        )
        if choice != t("event_log_all_types"):
            events = [e for e in events if e.get("event_type") == choice]
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)


def main() -> None:
    _bootstrap_openclaw_env()
    st.set_page_config(
        page_title=LANG.get("zh", {}).get("page_title", "OpenClaw"),
        layout="wide",
        initial_sidebar_state="expanded",
    )
    if "lang" not in st.session_state:
        st.session_state["lang"] = "zh"
    if "ui_theme" not in st.session_state:
        st.session_state["ui_theme"] = "light"
    _sync_theme_from_query()
    _inject_dashboard_styles(st.session_state.get("ui_theme", "light"))
    _require_dashboard_auth()
    render_disclaimer_banner()
    _mvp_ws = UserWorkspace()
    mvp_user = render_user_login_sidebar(_mvp_ws)

    with st.sidebar:
        st.markdown(
            "<div class='sidebar-brand'>OpenClaw</div>"
            "<div class='sidebar-title'>AI Picks</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='sidebar-status-fixed'>",
            unsafe_allow_html=True,
        )
        _render_openclaw_sidebar()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            "<div class='sidebar-toolbar'>"
            "<div class='sidebar-toolbar-label'>Controls</div>"
            "<div class='sidebar-toolbar-actions'>"
            "<span class='sidebar-toolbar-chip'>Locale</span>"
            "<span class='sidebar-toolbar-chip'>Theme</span>"
            "<span class='sidebar-toolbar-chip'>Refresh</span>"
            "</div></div>",
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
        if isinstance(sel, tuple) and sel[0] != cur:
            st.session_state["lang"] = sel[0]
            try:
                from opinion_trading.core.settings_patch import update_explanation_lang

                cfg_path = str(Path("config/settings.yaml").resolve())
                if Path(cfg_path).is_file():
                    update_explanation_lang(cfg_path, sel[0])
            except Exception:
                pass

        theme_opts = [
            ("light", t("ui_theme_light")),
            ("dark", t("ui_theme_dark")),
        ]
        theme_cur = st.session_state.get("ui_theme", "light")
        theme_idx = 0 if theme_cur == "light" else 1
        theme_sel = st.radio(
            t("ui_theme_label"),
            options=theme_opts,
            index=theme_idx,
            key="_theme_display",
            format_func=lambda x: x[1],
            horizontal=True,
        )
        if isinstance(theme_sel, tuple) and theme_sel[0] != theme_cur:
            st.session_state["ui_theme"] = theme_sel[0]
            _persist_theme_query(theme_sel[0])
            st.rerun()
        else:
            _persist_theme_query(str(theme_cur))

        if st.button(t("refresh_data"), use_container_width=True):
            try:
                st.cache_data.clear()
            except Exception:
                pass
            for k in list(st.session_state.keys()):
                if str(k).startswith("_openclaw_probe_"):
                    st.session_state.pop(k, None)
            st.rerun()

        st.markdown(f"<div class='panel-rail panel-rail--compact'><div class='panel-section-title'>{t('sidebar_paths')}</div>", unsafe_allow_html=True)
        report_dir = st.text_input(t("report_dir"), "data/reports")
        raw_dir = st.text_input(t("raw_dir"), "data/raw")
        memory_dir = st.text_input(t("memory_dir"), "data/memory")
        st.markdown("</div>", unsafe_allow_html=True)
        _render_export_zip_button(report_dir, memory_dir, raw_dir)
        _render_collect_progress_expander(report_dir)

        with st.expander(t("settings_preview_title"), expanded=False):
            try:
                from opinion_trading.core.config_loader import load_runtime_config

                cfg = load_runtime_config("config/settings.yaml")
                rec = cfg.sentiment_recency
                st.caption(t("settings_preview_hint"))
                st.json(
                    {
                        "universe_symbols": cfg.symbols[:12],
                        "analysis_enabled": bool(
                            cfg.analysis and cfg.analysis.enabled
                        ),
                        "sentiment_recency": {
                            "enabled": bool(rec and rec.enabled),
                            "half_life_hours": rec.half_life_hours if rec else 24,
                        },
                        "risk": {
                            "max_single_symbol_notional_pct": (
                                cfg.risk.max_single_symbol_notional_pct
                                if cfg.risk
                                else 0.25
                            ),
                        },
                        "execution_mode": (
                            cfg.execution.mode if cfg.execution else "paper"
                        ),
                    }
                )
            except Exception as exc:
                st.caption(str(exc))

        with st.expander(t("universe_edit_title"), expanded=False):
            cfg_path = "config/settings.yaml"
            try:
                from opinion_trading.core.config_loader import load_runtime_config
                from opinion_trading.core.settings_patch import (
                    parse_symbol_list,
                    update_universe_symbols,
                )

                cur = load_runtime_config(cfg_path)
                default_text = "\n".join(cur.symbols)
                sym_text = st.text_area(
                    t("universe_edit_label"),
                    value=default_text,
                    height=120,
                    key="universe_edit_area",
                )
                st.caption(t("explanation_lang_hint"))
                if st.button(t("universe_save"), key="universe_save_btn"):
                    syms = parse_symbol_list(sym_text)
                    if not syms:
                        st.warning("empty symbol list")
                    else:
                        update_universe_symbols(cfg_path, syms)
                        st.success(t("universe_saved"))
            except Exception as exc:
                st.caption(str(exc))

        with st.expander(t("quick_start"), expanded=False):
            st.markdown(t("tutorial_markdown"))
        with st.expander(t("deploy_aliyun_title"), expanded=False):
            st.caption(t("deploy_aliyun_hint"))
            st.markdown(
                "See **[docs/deploy-aliyun-realtime.md](docs/deploy-aliyun-realtime.md)** "
                "and `deploy/aliyun/` (systemd + `openclaw.env.example`)."
            )

    picks_df = _load_latest_realtime_picks(report_dir)
    alerts_df = _load_latest_alerts(report_dir)
    sentiment_df = _load_sentiment_history(
        str(Path(memory_dir) / "sentiment_history.jsonl")
    )
    raw_raw = _load_latest_raw_posts(raw_dir)
    raw_df, clean_stats = prepare_customer_raw(raw_raw)
    picks_derived = False
    # Prefer denser derived picks when CSV is thin (<5 symbols) — local demo often
    # has only 1–2 rows in the newest realtime_picks while merged raw has more.
    if picks_df.empty or len(picks_df) < 5:
        from_raw = _picks_from_raw(raw_df, top_n=10)
        from_sent = _picks_from_sentiment(sentiment_df, top_n=10)
        candidates = [c for c in (from_raw, from_sent, picks_df) if c is not None and not c.empty]
        if candidates:
            picks_df = max(candidates, key=lambda d: len(d))
            src = (
                str(picks_df["_source_path"].iloc[0])
                if "_source_path" in picks_df.columns and len(picks_df)
                else ""
            )
            picks_derived = src.startswith("derived")
    platform_count = 0 if sentiment_df.empty else sentiment_df["platform"].nunique()
    engine_stats = build_sentiment_engine_stats(raw_df)
    capture_rates = compute_raw_capture_rates(raw_df)

    st.caption(
        _data_freshness_caption(
            picks_df, raw_df, sentiment_df, clean_stats=clean_stats
        )
    )
    if picks_derived:
        st.info(
            "推荐列表已根据有效帖文自动汇总。"
            "完整刷新可运行日批 / 实时选股。"
        )
    elif picks_df.empty and raw_df.empty and sentiment_df.empty:
        st.warning(
            "本地几乎没有展示数据。请先运行日批采集，"
            "或把侧边栏路径指到 data/reports、data/raw、data/memory。"
        )
    elif int(clean_stats.get("dropped_total", 0) or 0) > 0:
        st.caption(
            t("data_clean_fmt").format(
                kept=int(clean_stats.get("kept", 0) or 0),
                dropped=int(clean_stats.get("dropped_total", 0) or 0),
            )
        )

    _render_dashboard_hero(
        len(picks_df),
        len(alerts_df),
        platform_count,
        report_dir,
        picks_df=picks_df,
        engine_stats=engine_stats,
        capture_rates=capture_rates,
        clean_stats=clean_stats,
    )
    _render_sentiment_engine_strip(
        engine_stats, capture_rates=capture_rates, clean_stats=clean_stats
    )
    with st.expander(t("user_guide_title"), expanded=False):
        st.markdown(t("user_guide_body"))
    oc_probe = _openclaw_probe(llm=False)
    _render_status_strip(
        report_dir,
        len(picks_df),
        len(alerts_df),
        platform_count,
        openclaw_connected=bool(oc_probe.get("connected")),
    )

    tab_watch, tab_alert, tab_review, tab_ai, tab_picks, tab_openclaw, tab_sentiment, tab_comments, tab_eval, tab_analyst = st.tabs(
        [
            "自选股监控",
            "信号预警",
            "舆情股价复盘",
            "AI采集筛选",
            t("tab_picks"),
            t("tab_openclaw"),
            t("tab_sentiment"),
            t("tab_comments"),
            t("tab_eval"),
            t("tab_analyst"),
        ]
    )

    with tab_watch:
        render_watchlist_tab(sentiment_df, raw_df, mvp_user, workspace=_mvp_ws)

    with tab_alert:
        render_alerts_tab(sentiment_df, mvp_user, workspace=_mvp_ws)

    with tab_review:
        render_review_tab(sentiment_df, raw_df, mvp_user, workspace=_mvp_ws)

    with tab_ai:
        render_ai_pipeline_tab(raw_df)

    with tab_picks:
        _render_pick_leaderboard(picks_df)

        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown(f"#### {t('score_alerts')}")
        if alerts_df.empty:
            st.info(t("no_alerts"))
        else:
            st.dataframe(alerts_df, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(f"#### {t('pick_reason_cards')}")
        if picks_df.empty:
            st.info(t("run_realtime_daily_first"))
        else:
            _render_reason_cards(raw_df, picks_df, sentiment_df, lookback_days=30)

    with tab_openclaw:
        _render_openclaw_tab(raw_df, picks_df, report_dir)

    with tab_sentiment:
        st.markdown(
            "<div class='panel-rail'>"
            "<div class='panel-headbar'>"
            "<div class='panel-headbar-left'>"
            f"<div class='panel-section-title'>{t('sentiment_trend')}</div>"
            f"<div class='panel-subtitle'>{t('guide_trend_body')}</div>"
            "</div>"
            "<div class='panel-headbar-right'>"
            f"<span class='panel-headbar-chip'>{t('chip_trend')}</span>"
            f"<span class='panel-headbar-chip'>{t('chip_multisource')}</span>"
            "</div>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            c_filter, c_stats, c_export = st.columns([1.4, 1.0, 1.0])
            with c_filter:
                st.markdown(
                    f"<div class='panel-control-row'><div class='panel-control-label'>"
                    f"{t('filter_controls')}</div>",
                    unsafe_allow_html=True,
                )
                min_samples = st.number_input(
                    t("min_samples_platform"),
                    min_value=0,
                    value=1,
                    step=1,
                )
                include_zero = st.checkbox(
                    t("include_zero_scores"), value=True
                )
                try:
                    st.session_state["include_zero_scores"] = bool(include_zero)
                except Exception:
                    pass
                st.markdown(
                    f"<div class='panel-control-hint'>"
                    f"{t('filter_hint_samples')}"
                    "</div></div>",
                    unsafe_allow_html=True,
                )
            with c_stats:
                st.markdown(
                    f"<div class='panel-control-row'><div class='panel-control-label'>"
                    f"{t('signal_stats')}</div>",
                    unsafe_allow_html=True,
                )
                show_counts = st.checkbox(t("show_platform_counts"), value=True)
                st.markdown(
                    f"<div class='panel-control-hint'>{t('signal_stats_hint')}</div></div>",
                    unsafe_allow_html=True,
                )
            with c_export:
                st.markdown(
                    f"<div class='panel-control-row'><div class='panel-control-label'>"
                    f"{t('export_section')}</div>",
                    unsafe_allow_html=True,
                )
                export_placeholder = st.empty()
                st.markdown(
                    f"<div class='panel-control-hint'>{t('export_hint')}</div></div>",
                    unsafe_allow_html=True,
                )

            if not sentiment_df.empty:
                df = sentiment_df.copy()
                df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
                df["sentiment_score"] = pd.to_numeric(
                    df.get("sentiment_score", None), errors="coerce"
                )
                if not include_zero:
                    df.loc[df["sentiment_score"] == 0.0, "sentiment_score"] = pd.NA
                df["month"] = df["trade_date"].dt.to_period("M").astype(str)
                if "post_count" in df.columns:
                    df["post_count"] = pd.to_numeric(
                        df.get("post_count", 1), errors="coerce"
                    ).fillna(1)
                    tmp2 = df.dropna(subset=["sentiment_score"]).copy()
                    if tmp2.empty:
                        grouped = pd.DataFrame(columns=["month", "platform", "sentiment_score"])
                    else:
                        tmp2["_weighted"] = tmp2["sentiment_score"] * tmp2["post_count"]
                        sums = tmp2.groupby(["month", "platform"])["post_count"].sum()
                        numer = tmp2.groupby(["month", "platform"])["_weighted"].sum()
                        series = numer / sums
                        idx = pd.DataFrame(list(series.index), columns=["month", "platform"])
                        grouped = pd.concat([idx.reset_index(drop=True), pd.DataFrame({"sentiment_score": list(series.values)})], axis=1)
                else:
                    grouped = df.dropna(subset=["sentiment_score"]).groupby(["month", "platform"], as_index=False)["sentiment_score"].mean()

                if grouped.empty:
                    st.info(t("no_sentiment_history"))
                else:
                    counts = df.dropna(subset=["sentiment_score"]).groupby("platform").size().reset_index(name="samples")
                    valid_platforms = counts[counts["samples"] >= int(min_samples)]["platform"].tolist()
                    filtered = grouped[grouped["platform"].isin(valid_platforms)].copy()
                    if show_counts:
                        st.markdown(
                            f"<div class='panel-control-row'><div class='panel-control-label'>"
                            f"{t('platform_sample_counts')}</div><div class='panel-control-hint'>"
                            + ", ".join([f"{_platform_label(str(r['platform']))}={r['samples']}" for _, r in counts.iterrows()])
                            + "</div></div>",
                            unsafe_allow_html=True,
                        )
                    if filtered.empty:
                        st.warning(t("no_platforms_after_filter"))
                    else:
                        export_placeholder.download_button(
                            label=t("download_csv"),
                            data=filtered.to_csv(index=False).encode("utf-8"),
                            file_name="agg_monthly_filtered.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )
                        st.markdown("<div class='chart-shell'>", unsafe_allow_html=True)
                        chart_df = label_platform_column(filtered, _ui_lang())
                        chart = alt.Chart(chart_df).mark_line(point=True, strokeWidth=2.2).encode(
                            x=alt.X("month:N", title=t("month")),
                            y=alt.Y("sentiment_score:Q", title=t("sentiment_score_label")),
                            color=alt.Color("platform:N", scale=alt.Scale(range=_DASH_COLORS), title=t("platform_label")),
                            tooltip=["month", "platform", "sentiment_score"],
                        ).properties(title=t("sentiment_trend"), height=280)
                        st.altair_chart(_configure_chart(chart), use_container_width=True)
                        st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info(t("no_sentiment_history"))

        st.markdown(
            "<div class='panel-rail panel-rail--compact'>"
            "<div class='panel-headbar'>"
            "<div class='panel-headbar-left'>"
            f"<div class='panel-section-title'>{t('platform_contribution')}</div>"
            f"<div class='panel-subtitle'>{t('guide_contrib_body')}</div>"
            "</div>"
            "<div class='panel-headbar-right'>"
            f"<span class='panel-headbar-chip'>{t('chip_drivers')}</span>"
            f"<span class='panel-headbar-chip'>{t('chip_weights')}</span>"
            "</div>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            c_left, c_mid, c_right = st.columns([1.2, 1.0, 0.9])
            pick_symbols = sorted(picks_df["symbol"].unique()) if not picks_df.empty else []
            hist_symbols = sorted(sentiment_df["symbol"].unique()) if not sentiment_df.empty else []
            symbol_options = sorted(set(pick_symbols + hist_symbols))
            if not symbol_options:
                st.info(t("no_contribution_data"))
            else:
                with c_left:
                    symbol = st.selectbox(t("select_symbol_for_contribution"), symbol_options)
                with c_mid:
                    lookback_days = st.number_input(t("lookback_days_non_zero"), min_value=1, value=30, step=1)
                with c_right:
                    st.markdown(
                        f"<div class='panel-control-row'><div class='panel-control-label'>{t('actions')}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div class='panel-control-hint'>{t('contrib_actions_hint')}</div></div>",
                        unsafe_allow_html=True,
                    )
                contrib_df = build_pick_contribution(symbol, picks_df, raw_df, sentiment_df, lookback_days=int(lookback_days))
                if contrib_df.empty:
                    st.info(t("no_contribution_data"))
                else:
                    avg_score = 0.0
                    if not picks_df.empty:
                        pr = picks_df[picks_df["symbol"] == symbol].head(1)
                        if not pr.empty:
                            avg_score = float(pd.to_numeric(pr["avg_score"], errors="coerce").fillna(0))
                    st.markdown(build_pick_narrative(symbol, avg_score, contrib_df, raw_df, lang=st.session_state.get("lang", "zh")))
                    stats = evidence_stats(raw_df, symbol)
                    st.caption(_evidence_caption(stats))
                    if stats["valid"] < 8:
                        st.warning(t("sample_low_warning"))
                    display_df = label_platform_column(contrib_df, _ui_lang())[["platform", "platform_score", "config_weight", "weighted_contrib", "weight_pct", "observations", "direction"]].rename(columns={"platform": t("col_platform"), "platform_score": t("col_platform_score"), "config_weight": t("col_config_weight"), "weighted_contrib": t("col_weighted_contrib"), "weight_pct": t("col_weight_pct"), "observations": t("col_observations"), "direction": t("col_direction")})
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    st.markdown("<div class='chart-shell'>", unsafe_allow_html=True)
                    chart_view = contrib_df[contrib_df["platform_score"].abs() > 0.001].copy()
                    if chart_view.empty:
                        chart_view = contrib_df.copy()
                    chart_view = label_platform_column(chart_view, _ui_lang())
                    chart_view["bar_color"] = chart_view["platform_score"].apply(lambda s: "bull" if s > 0.05 else "bear" if s < -0.05 else "flat")
                    bar = alt.Chart(chart_view).mark_bar(cornerRadiusEnd=12).encode(
                        x=alt.X("weighted_contrib:Q", title=t("col_weighted_contrib")),
                        y=alt.Y("platform:N", sort="-x", title=None),
                        color=alt.Color("bar_color:N", scale=_SENTIMENT_BAR_SCALE, title=t("col_direction")),
                        tooltip=["platform", "platform_score", "config_weight", "weighted_contrib", "weight_pct", "observations"],
                    ).properties(title=t("platform_contribution"), height=280)
                    st.altair_chart(_configure_chart(bar), use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            "<div class='panel-rail panel-rail--compact'>"
            "<div class='panel-headbar'>"
            "<div class='panel-headbar-left'>"
            f"<div class='panel-section-title'>{t('platform_snapshot')}</div>"
            f"<div class='panel-subtitle'>{t('guide_snapshot_body')}</div>"
            "</div>"
            "<div class='panel-headbar-right'>"
            f"<span class='panel-headbar-chip'>{t('chip_snapshot')}</span>"
            f"<span class='panel-headbar-chip'>{t('chip_ranked')}</span>"
            "</div>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        pick_symbols = sorted(picks_df["symbol"].unique()) if not picks_df.empty else []
        hist_symbols = sorted(sentiment_df["symbol"].unique()) if not sentiment_df.empty else []
        snapshot_options = sorted(set(pick_symbols + hist_symbols))
        snapshot_symbol = st.selectbox(t("select_symbol_for_radar"), snapshot_options if snapshot_options else [""])
        with st.container(border=True):
            if not snapshot_symbol:
                st.info(t("no_radar_data"))
            else:
                snap = build_pick_contribution(snapshot_symbol, picks_df, raw_df, sentiment_df, lookback_days=30)
                if snap.empty:
                    st.info(t("no_radar_data"))
                else:
                    snap_display = label_platform_column(snap, _ui_lang())
                    snap_display["sentiment_label"] = snap_display["platform_score"].apply(lambda s: f"{s:+.3f}")
                    snap_display["bar_color"] = snap_display["platform_score"].apply(lambda s: "bull" if s > 0.05 else "bear" if s < -0.05 else "flat")
                    snap_chart = alt.Chart(snap_display).mark_bar(cornerRadiusEnd=12).encode(
                        x=alt.X("platform_score:Q", title=t("sentiment_score_label")),
                        y=alt.Y("platform:N", sort="-x", title=t("platform_label")),
                        color=alt.Color("bar_color:N", scale=_SENTIMENT_BAR_SCALE, title=t("col_direction")),
                        tooltip=["platform", "platform_score", "observations", "weight_pct"],
                    ).properties(height=max(220, 36 * len(snap_display)))
                    st.altair_chart(_configure_chart(snap_chart), use_container_width=True)
                    st.dataframe(
                        snap_display[["platform", "platform_score", "observations", "weight_pct", "direction"]].rename(columns={"platform": t("col_platform"), "platform_score": t("col_platform_score"), "observations": t("col_observations"), "weight_pct": t("col_weight_pct"), "direction": t("col_direction")}),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

    with tab_comments:
        _render_info_box(t("guide_comments_title"), t("guide_comments_body"))
        st.markdown(f"#### {t('top_comments')}")
        if raw_df.empty:
            st.info(t("no_raw_posts"))
        else:
            sel_symbol = st.selectbox(
                t("select_symbol"), sorted(raw_df["symbol"].unique())
            )
            _render_symbol_sentiment_card(raw_df, sel_symbol)
            stats = evidence_stats(raw_df, sel_symbol)
            st.caption(_evidence_caption(stats))
            if stats["valid"] < 5:
                st.warning(t("sample_low_warning"))
            if stats["valid"] < 3:
                st.info(t("comments_few_hint"))

            top_rows = top_comment_rows(
                raw_df, sel_symbol, top_n=10, include_reference=True, ref_n=4
            )
            comment_cols = st.columns(2)
            with comment_cols[0]:
                st.markdown(
                    f"<div class='comment-panel'><div class='comment-panel-title'>"
                    f"{t('positive_highlight')} ({len(top_rows['positive'])})</div>",
                    unsafe_allow_html=True,
                )
                _render_comment_highlights(
                    top_rows["positive"],
                    key_prefix=f"tab_pos_{sel_symbol}",
                    empty_message=None,
                )
                if top_rows["positive"].empty:
                    st.info(t("no_valid_comments"))
                st.markdown("</div>", unsafe_allow_html=True)
            with comment_cols[1]:
                st.markdown(
                    f"<div class='comment-panel'><div class='comment-panel-title'>"
                    f"{t('negative_highlight')} ({len(top_rows['negative'])})</div>",
                    unsafe_allow_html=True,
                )
                _render_comment_highlights(
                    top_rows["negative"],
                    key_prefix=f"tab_neg_{sel_symbol}",
                    empty_message=None,
                )
                if top_rows["negative"].empty:
                    st.info(t("no_valid_comments"))
                st.markdown("</div>", unsafe_allow_html=True)
            if not top_rows["reference"].empty:
                with st.expander(
                    f"{t('reference_expand_hint')} ({len(top_rows['reference'])})",
                    expanded=False,
                ):
                    _render_comment_highlights(
                        top_rows["reference"],
                        key_prefix=f"tab_ref_{sel_symbol}",
                        empty_message=None,
                        use_expanders=False,
                    )

    with tab_eval:
        _render_paper_account_panel(memory_dir)
        _render_quality_gate_history_chart(memory_dir)
        _render_event_log_panel(memory_dir)
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
                st.caption(
                    f"Max DD {summary.max_drawdown:.2%} | "
                    f"Profit factor {summary.profit_factor:.3f} | "
                    f"Payoff {summary.payoff_ratio:.3f} | "
                    f"Calmar-like {summary.calmar_like:.4f}"
                )
                if not merged.empty:
                    st.dataframe(
                        merged[
                            ["trade_date", "symbol", "action", "next_return", "correct"]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
                st.session_state["eval_price_df"] = price_df
            except Exception as e:
                st.error(t("evaluation_failed").format(error=e))

        wf_price = st.session_state.get("eval_price_df")
        if wf_price is None or (isinstance(wf_price, pd.DataFrame) and wf_price.empty):
            try:
                wf_price = load_prices(price_csv)
            except Exception:
                wf_price = pd.DataFrame()
        _render_walk_forward_panel(memory_dir, report_dir, wf_price, auto_run=False)

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
                        .mark_bar(cornerRadiusEnd=12)
                        .encode(
                            x=alt.X("month:N", title=t("month")),
                            y=alt.Y("signals:Q", title=t("signal_count")),
                            color=alt.Color(
                                "accuracy:Q",
                                scale=alt.Scale(
                                    range=["#EDE6DC", "#8B7355", "#5C534A"]
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

    with tab_analyst:
        _render_analyst_tab(memory_dir, report_dir)


if __name__ == "__main__":
    main()
