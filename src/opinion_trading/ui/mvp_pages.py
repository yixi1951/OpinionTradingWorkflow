"""Streamlit MVP pages: watchlist / alerts / sentiment-price review."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import altair as alt
import pandas as pd
import streamlit as st

from opinion_trading.core.symbol_explain import explain_symbol_sentiment
from opinion_trading.core.user_workspace import AlertRule, UserWorkspace
from opinion_trading.core.watchlist_alerts import run_watchlist_alert_cycle


DISCLAIMER_ZH = (
    "本系统仅为舆情数据统计分析，不构成任何投资建议。"
    "股市有风险，投资需谨慎。数据采集遵循公开信息与平台规范，不爬取非公开或隐私数据。"
)


def render_disclaimer_banner() -> None:
    st.markdown(
        f"<div class='disclaimer-banner disclaimer-banner--compact'>"
        f"<strong>免责声明</strong>"
        f"<span class='disclaimer-banner-text'>{DISCLAIMER_ZH}</span></div>",
        unsafe_allow_html=True,
    )


def render_user_login_sidebar(workspace: Optional[UserWorkspace] = None) -> str:
    """Simple multi-user login (demo/demo123). Returns username."""
    ws = workspace or UserWorkspace()
    st.sidebar.markdown("### 账号")
    if st.session_state.get("mvp_user"):
        st.sidebar.success(f"已登录：{st.session_state['mvp_user']}")
        if st.sidebar.button("退出登录", key="mvp_logout"):
            st.session_state.pop("mvp_user", None)
            st.rerun()
        return str(st.session_state["mvp_user"])

    mode = st.sidebar.radio("登录 / 注册", ["登录", "注册"], horizontal=True, key="mvp_auth_mode")
    username = st.sidebar.text_input("用户名", value="demo", key="mvp_username")
    password = st.sidebar.text_input("密码", type="password", value="demo123", key="mvp_password")
    email = ""
    if mode == "注册":
        email = st.sidebar.text_input("邮箱（可选，用于预警）", key="mvp_email")
        if st.sidebar.button("注册", key="mvp_register_btn"):
            try:
                ws.register(username.strip(), password, email=email.strip())
                st.sidebar.success("注册成功，请登录")
            except Exception as exc:
                st.sidebar.error(str(exc))
    else:
        if st.sidebar.button("登录", key="mvp_login_btn"):
            profile = ws.authenticate(username.strip(), password)
            if profile:
                st.session_state["mvp_user"] = profile.username
                st.rerun()
            else:
                st.sidebar.error("用户名或密码错误（演示账号 demo / demo123）")
    return str(st.session_state.get("mvp_user") or "demo")


def _symbol_daily_sentiment(sentiment_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if sentiment_df.empty:
        return pd.DataFrame(columns=["trade_date", "score", "heat"])
    sub = sentiment_df[sentiment_df["symbol"].astype(str).str.upper() == symbol.upper()].copy()
    if sub.empty or "sentiment_score" not in sub.columns:
        return pd.DataFrame(columns=["trade_date", "score", "heat"])
    sub["trade_date"] = pd.to_datetime(sub.get("trade_date"), errors="coerce")
    sub = sub.dropna(subset=["trade_date"])
    if "post_count" in sub.columns:
        daily = (
            sub.groupby(sub["trade_date"].dt.date)
            .agg(score=("sentiment_score", "mean"), heat=("post_count", "sum"))
            .reset_index()
        )
    else:
        daily = (
            sub.groupby(sub["trade_date"].dt.date)
            .agg(score=("sentiment_score", "mean"), heat=("sentiment_score", "count"))
            .reset_index()
        )
    daily.columns = ["trade_date", "score", "heat"]
    daily["trade_date"] = pd.to_datetime(daily["trade_date"])
    return daily.sort_values("trade_date")


@st.cache_data(ttl=3600, show_spinner=False)
def _load_price_series(symbol: str, lookback_days: int = 90) -> pd.DataFrame:
    """Cached OHLCV — review tab runs on every Streamlit rerun, so uncached
    akshare/yfinance calls (~10s) make the whole dashboard feel stuck on RUNNING.
    """
    try:
        from opinion_trading.core.market_data import fetch_ohlcv

        end = date.today()
        start = end - timedelta(days=lookback_days)
        df = fetch_ohlcv(symbol, start_date=start.isoformat(), end_date=end.isoformat())
        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "close"])
        out = df.reset_index() if "Close" in getattr(df, "columns", []) or "close" in [
            c.lower() for c in getattr(df, "columns", [])
        ] else df.copy()
        # normalize columns
        cols = {c.lower(): c for c in out.columns}
        date_col = cols.get("date") or cols.get("datetime") or out.columns[0]
        close_col = cols.get("close") or cols.get("adj close")
        if close_col is None:
            for c in out.columns:
                if str(c).lower() == "close":
                    close_col = c
                    break
        if close_col is None:
            return pd.DataFrame(columns=["date", "close"])
        res = pd.DataFrame(
            {
                "date": pd.to_datetime(out[date_col], errors="coerce"),
                "close": pd.to_numeric(out[close_col], errors="coerce"),
            }
        ).dropna()
        return res.sort_values("date")
    except Exception:
        return pd.DataFrame(columns=["date", "close"])


def render_watchlist_tab(
    sentiment_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    username: str,
    workspace: Optional[UserWorkspace] = None,
) -> None:
    ws = workspace or UserWorkspace()
    profile = ws.load_profile(username) or ws.load_profile("demo")
    assert profile is not None

    st.subheader("自选股舆情监控")
    st.caption("聚焦你关注的标的：情感趋势、关键言论与可解释摘要（非全市场榜单）。")

    c1, c2 = st.columns([3, 1])
    with c1:
        new_sym = st.text_input("添加自选股（如 600519.SH）", key="mvp_add_sym")
    with c2:
        st.write("")
        if st.button("添加", key="mvp_add_btn"):
            if new_sym.strip():
                ws.add_watch(profile.username, new_sym.strip())
                st.rerun()

    if not profile.watchlist:
        st.info("自选股为空，请先添加。")
        return

    symbol = st.selectbox("选择自选股", profile.watchlist, key="mvp_watch_select")
    if st.button("移出自选", key="mvp_remove_btn"):
        ws.remove_watch(profile.username, symbol)
        st.rerun()

    daily = _symbol_daily_sentiment(sentiment_df, symbol)
    expl = explain_symbol_sentiment(symbol, sentiment_df=sentiment_df, raw_df=raw_df)

    m1, m2, m3 = st.columns(3)
    m1.metric("最新情感分", f"{expl['score']:+.3f}" if expl["score"] is not None else "—")
    m2.metric("方向", expl["direction"])
    m3.metric("事件类型", ", ".join(expl["event_types"]) or "—")

    st.markdown(f"**为什么舆情分是这样？** {expl['summary']}")

    if not daily.empty:
        chart = (
            alt.Chart(daily)
            .mark_line(point=True)
            .encode(
                x=alt.X("trade_date:T", title="日期"),
                y=alt.Y("score:Q", title="情感分"),
                tooltip=["trade_date", "score", "heat"],
            )
            .properties(height=260, title=f"{symbol} 舆情情感趋势")
        )
        st.altair_chart(chart, use_container_width=True)
        heat = (
            alt.Chart(daily)
            .mark_bar(opacity=0.7)
            .encode(
                x=alt.X("trade_date:T", title="日期"),
                y=alt.Y("heat:Q", title="热度(帖量)"),
                tooltip=["trade_date", "heat"],
            )
            .properties(height=160, title="舆情热度")
        )
        st.altair_chart(heat, use_container_width=True)
    else:
        st.warning("暂无该标的情感历史，请先跑 daily/realtime。")

    st.markdown("#### 关键言论")
    if expl["key_comments"]:
        st.dataframe(pd.DataFrame(expl["key_comments"]), use_container_width=True, hide_index=True)
    else:
        st.caption("暂无关键评论样本。")


def render_alerts_tab(
    sentiment_df: pd.DataFrame,
    username: str,
    workspace: Optional[UserWorkspace] = None,
) -> None:
    ws = workspace or UserWorkspace()
    profile = ws.load_profile(username) or ws.load_profile("demo")
    assert profile is not None

    st.subheader("信号预警推送")
    st.caption("设置情感分阈值 / 热度突增倍数；触发后写入站内信，并尝试邮件与企微/钉钉推送。")

    symbols = profile.watchlist or ["600519.SH"]
    sym = st.selectbox("预警标的", symbols, key="mvp_alert_sym")
    existing = next(
        (r for r in profile.alert_rules if str(r.get("symbol", "")).upper() == sym.upper()),
        {},
    )
    c1, c2, c3 = st.columns(3)
    score_high = c1.number_input(
        "情感分上限阈值", value=float(existing.get("score_high", 0.35)), step=0.05
    )
    score_low = c2.number_input(
        "情感分下限阈值", value=float(existing.get("score_low", -0.35)), step=0.05
    )
    heat_ratio = c3.number_input(
        "热度突增倍数", value=float(existing.get("heat_spike_ratio", 2.0)), step=0.1, min_value=1.0
    )
    email = st.text_input("预警邮箱", value=profile.email or "", key="mvp_alert_email")
    if st.button("保存预警规则", key="mvp_save_alert"):
        profile.email = email.strip()
        ws.save_profile(profile)
        ws.upsert_alert_rule(
            profile.username,
            AlertRule(
                symbol=sym,
                score_high=float(score_high),
                score_low=float(score_low),
                heat_spike_ratio=float(heat_ratio),
                enabled=True,
            ),
        )
        st.success("已保存")

    if st.button("立即检查并推送", key="mvp_run_alerts"):
        results = run_watchlist_alert_cycle(profile.username, sentiment_df, workspace=ws)
        if not results:
            st.info("当前未触发任何预警。")
        else:
            st.success(f"触发 {len(results)} 条预警")
            st.json(results)

    st.markdown("#### 站内信")
    inbox = ws.list_inbox(profile.username, limit=30)
    if not inbox:
        st.caption("暂无站内信。")
    else:
        st.dataframe(pd.DataFrame(inbox), use_container_width=True, hide_index=True)
        if st.button("全部标为已读", key="mvp_inbox_read"):
            ws.mark_inbox_read(profile.username)
            st.rerun()


def render_review_tab(
    sentiment_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    username: str,
    workspace: Optional[UserWorkspace] = None,
) -> None:
    ws = workspace or UserWorkspace()
    profile = ws.load_profile(username) or ws.load_profile("demo")
    assert profile is not None

    st.subheader("舆情 — 股价联动复盘")
    st.caption("叠加舆情走势与收盘价，回溯事件类型，验证信号是否领先于价格。")

    symbols = profile.watchlist or ["600519.SH"]
    symbol = st.selectbox("复盘标的", symbols, key="mvp_review_sym")
    lookback = st.slider("回看天数", 30, 180, 90, key="mvp_review_lb")
    load_prices = st.checkbox(
        "叠加股价（首次约需几秒拉取行情）",
        value=False,
        key="mvp_review_load_prices",
    )

    daily = _symbol_daily_sentiment(sentiment_df, symbol)
    prices = (
        _load_price_series(symbol, lookback_days=lookback)
        if load_prices
        else pd.DataFrame(columns=["date", "close"])
    )
    expl = explain_symbol_sentiment(symbol, sentiment_df=sentiment_df, raw_df=raw_df)

    if daily.empty and prices.empty:
        st.warning("缺少舆情或行情数据。" + ("" if load_prices else " 可勾选上方选项叠加股价。"))
        return

    frames = []
    if not daily.empty:
        s = daily.rename(columns={"trade_date": "date", "score": "value"})
        s["series"] = "舆情情感分"
        frames.append(s[["date", "value", "series"]])
    if not prices.empty:
        # normalize price to z-ish scale for dual view: use pct from first
        p = prices.copy()
        base = float(p["close"].iloc[0]) or 1.0
        p["value"] = p["close"] / base - 1.0
        p["series"] = "股价累计涨跌"
        frames.append(p[["date", "value", "series"]])
    if frames:
        plot_df = pd.concat(frames, ignore_index=True)
        chart = (
            alt.Chart(plot_df)
            .mark_line()
            .encode(
                x=alt.X("date:T", title="日期"),
                y=alt.Y("value:Q", title="舆情分 / 股价相对涨跌"),
                color="series:N",
                tooltip=["date", "series", "value"],
            )
            .properties(height=320, title=f"{symbol} 舆情 vs 股价")
        )
        st.altair_chart(chart, use_container_width=True)

    if not daily.empty and not prices.empty:
        merged = pd.merge_asof(
            daily.sort_values("trade_date"),
            prices.rename(columns={"date": "trade_date"}).sort_values("trade_date"),
            on="trade_date",
            direction="backward",
        )
        merged["next_ret_1d"] = merged["close"].pct_change().shift(-1)
        valid = merged.dropna(subset=["score", "next_ret_1d"])
        if len(valid) >= 5:
            corr = float(valid["score"].corr(valid["next_ret_1d"]))
            st.metric("舆情分 vs 次日收益 相关系数", f"{corr:+.3f}")

    st.markdown("#### 历史事件回溯（基于帖文事件分类）")
    st.write(expl["summary"])
    if expl["key_comments"]:
        st.dataframe(pd.DataFrame(expl["key_comments"]), use_container_width=True, hide_index=True)


def render_ai_pipeline_tab(raw_df: pd.DataFrame) -> None:
    """AI 采集与筛选：score_source / 相关度剔除 / 平台成功率样例。"""
    st.subheader("AI 采集与筛选")
    st.caption(
        "展示 LLM 相关度筛查与情感打分结果；Cookie 驱动的浏览器采集用于雪球/微博/抖音。"
        "关键词分仅作兜底，不作为主路径。"
    )
    if raw_df is None or raw_df.empty:
        st.info("暂无原始帖数据，请先运行 daily 采集。")
        return

    df = raw_df.copy()
    total = len(df)
    m1, m2, m3, m4 = st.columns(4)
    llm_n = 0
    if "score_source" in df.columns:
        src = df["score_source"].astype(str).str.lower()
        llm_n = int(src.isin(["openclaw", "transformers", "gateway", "hybrid"]).sum())
    relevant_n = (
        int(df["ai_relevant"].fillna(True).astype(bool).sum())
        if "ai_relevant" in df.columns
        else total
    )
    success_n = (
        int((df["capture_status"].astype(str) == "success").sum())
        if "capture_status" in df.columns
        else 0
    )
    m1.metric("原始帖", total)
    m2.metric("LLM 打分", f"{llm_n} ({llm_n / total:.0%})" if total else "0")
    m3.metric("AI 判定相关", f"{relevant_n} ({relevant_n / total:.0%})" if total else "0")
    m4.metric("采集成功", f"{success_n} ({success_n / total:.0%})" if total else "0")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### score_source 分布")
        if "score_source" in df.columns:
            st.dataframe(
                df["score_source"]
                .fillna("(na)")
                .astype(str)
                .value_counts()
                .rename("count")
                .reset_index(),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("无 score_source 列")
    with c2:
        st.markdown("#### 平台 × 采集状态")
        if "platform" in df.columns and "capture_status" in df.columns:
            ct = pd.crosstab(df["platform"], df["capture_status"].fillna("na"))
            st.dataframe(ct, use_container_width=True)
        else:
            st.caption("缺 platform/capture_status")

    if "ai_drop_reason" in df.columns and "ai_relevant" in df.columns:
        dropped = df[df["ai_relevant"].fillna(True).astype(bool) == False]  # noqa: E712
        if not dropped.empty:
            st.markdown("#### AI 剔除原因（Top）")
            st.dataframe(
                dropped["ai_drop_reason"]
                .fillna("(空)")
                .astype(str)
                .value_counts()
                .head(10)
                .rename("count")
                .reset_index(),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("#### 样例：相关帖 + 情感分")
    show_cols = [
        c
        for c in [
            "symbol",
            "platform",
            "title",
            "ai_score",
            "score_source",
            "ai_relevant",
            "capture_status",
            "event_type",
        ]
        if c in df.columns
    ]
    sample = df
    if "ai_relevant" in sample.columns:
        sample = sample[sample["ai_relevant"].fillna(True).astype(bool)]
    if "ai_score" in sample.columns and not sample.empty:
        sample = sample.assign(_abs=pd.to_numeric(sample["ai_score"], errors="coerce").abs())
        sample = sample.sort_values("_abs", ascending=False)
    st.dataframe(sample[show_cols].head(30), use_container_width=True, hide_index=True)
