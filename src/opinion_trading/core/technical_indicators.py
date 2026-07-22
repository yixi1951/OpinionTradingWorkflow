"""Technical indicators for stock price analysis.

All functions take a DataFrame with OHLCV columns and return a Series
or DataFrame with the indicator values appended.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add RSI (Relative Strength Index) column."""
    if df.empty or "Close" not in df.columns:
        return df
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df = df.copy()
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Add MACD, signal line, and histogram columns."""
    if df.empty or "Close" not in df.columns:
        return df
    df = df.copy()
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_Signal"] = df["MACD"].ewm(span=signal, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]
    return df


def add_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
) -> pd.DataFrame:
    """Add Bollinger Bands (Upper, Middle, Lower) and Bandwidth."""
    if df.empty or "Close" not in df.columns:
        return df
    df = df.copy()
    df["BB_Middle"] = df["Close"].rolling(window=period).mean()
    bb_std = df["Close"].rolling(window=period).std()
    df["BB_Upper"] = df["BB_Middle"] + std_dev * bb_std
    df["BB_Lower"] = df["BB_Middle"] - std_dev * bb_std
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Middle"]
    df["BB_Position"] = (df["Close"] - df["BB_Lower"]) / (df["BB_Upper"] - df["BB_Lower"]).replace(0, np.nan)
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add Average True Range (volatility indicator)."""
    if df.empty or not all(c in df.columns for c in ["High", "Low", "Close"]):
        return df
    df = df.copy()
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(span=period, adjust=False).mean()
    df["ATR_Pct"] = df["ATR"] / df["Close"] * 100
    return df


def add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add volume-based indicators (volume SMA, volume ratio)."""
    if df.empty or "Volume" not in df.columns:
        return df
    df = df.copy()
    df["Volume_SMA_20"] = df["Volume"].rolling(window=20).mean()
    df["Volume_Ratio"] = df["Volume"] / df["Volume_SMA_20"].replace(0, np.nan)
    df["Volume_Change"] = df["Volume"].pct_change()
    return df


def add_moving_averages(
    df: pd.DataFrame,
    windows: Tuple[int, ...] = (5, 10, 20, 60),
) -> pd.DataFrame:
    """Add simple moving averages for given windows."""
    if df.empty or "Close" not in df.columns:
        return df
    df = df.copy()
    for w in windows:
        df[f"SMA_{w}"] = df["Close"].rolling(window=w).mean()
        df[f"Price_vs_SMA_{w}"] = (df["Close"] - df[f"SMA_{w}"]) / df[f"SMA_{w}"].replace(0, np.nan)
    return df


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience: compute all indicators on a DataFrame."""
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger_bands(df)
    df = add_atr(df)
    df = add_volume_indicators(df)
    df = add_moving_averages(df)
    return df


# ── Scoring functions ─────────────────────────────────────────────────────


def score_trend(df: pd.DataFrame) -> float:
    """Score trend strength on latest row: -1 (strong downtrend) to +1 (strong uptrend)."""
    if df.empty or "Close" not in df.columns:
        return 0.0
    close = df["Close"]
    if len(close) < 20:
        return 0.0

    # Multi-timeframe trend
    sma_5 = close.rolling(5).mean().iloc[-1]
    sma_10 = close.rolling(10).mean().iloc[-1]
    sma_20 = close.rolling(20).mean().iloc[-1]
    current = close.iloc[-1]

    trends = [current > sma_5, sma_5 > sma_10, sma_10 > sma_20]
    score = (sum(trends) - 1.5) / 1.5  # maps [0,1,2,3] → [-1, -0.33, 0.33, 1]

    return max(-1.0, min(1.0, float(score)))


def score_momentum(df: pd.DataFrame) -> float:
    """Score momentum using RSI and MACD: -1 to +1."""
    if df.empty:
        return 0.0
    df_e = add_rsi(df)
    df_e = add_macd(df_e)

    score = 0.0
    count = 0

    # RSI contribution
    if "RSI" in df_e.columns and not df_e["RSI"].dropna().empty:
        rsi = float(df_e["RSI"].iloc[-1])
        rsi_score = (rsi - 50) / 50  # -1 at 0, 0 at 50, +1 at 100
        score += max(-1.0, min(1.0, rsi_score))
        count += 1

    # MACD contribution
    if "MACD_Hist" in df_e.columns and not df_e["MACD_Hist"].dropna().empty:
        macd_hist = float(df_e["MACD_Hist"].iloc[-1])
        macd_hist_prev = float(df_e["MACD_Hist"].iloc[-2]) if len(df_e) > 1 else 0.0
        macd_score = np.tanh(float(macd_hist) * 5)  # squash to (-1, 1)
        macd_trend = 1.0 if macd_hist > macd_hist_prev else -1.0 if macd_hist < macd_hist_prev else 0.0
        score += float(macd_score) * 0.7 + macd_trend * 0.3
        count += 1

    return max(-1.0, min(1.0, score / max(count, 1)))


def score_volatility(df: pd.DataFrame) -> float:
    """Score volatility regime using ATR and BB width: -1 (low vol) to +1 (high vol).

    High volatility → cautious (negative score direction).
    """
    if df.empty or len(df) < 20:
        return 0.0
    df_e = add_atr(df)
    df_e = add_bollinger_bands(df_e)

    score = 0.0
    count = 0

    if "ATR_Pct" in df_e.columns:
        atr = float(df_e["ATR_Pct"].dropna().iloc[-1]) if not df_e["ATR_Pct"].dropna().empty else 0.0
        # ATR > 5% is very high; < 1% is low
        atr_score = -max(-1.0, min(1.0, (atr - 2) / 3))
        score += atr_score
        count += 1

    if "BB_Width" in df_e.columns:
        bbw = float(df_e["BB_Width"].dropna().iloc[-1]) if not df_e["BB_Width"].dropna().empty else 0.0
        # BB Width > 0.5 is wide; < 0.1 is narrow
        bbw_score = -max(-1.0, min(1.0, (bbw - 0.2) / 0.3))
        score += bbw_score
        count += 1

    return max(-1.0, min(1.0, score / max(count, 1)))


def score_volume(df: pd.DataFrame) -> float:
    """Score volume trend: -1 (shrinking) to +1 (expanding, healthy)."""
    if df.empty or "Volume" not in df.columns:
        return 0.0
    df_e = add_volume_indicators(df)
    vol_ratio = float(df_e["Volume_Ratio"].dropna().iloc[-1]) if not df_e["Volume_Ratio"].dropna().empty else 1.0
    if vol_ratio > 2.0:
        return 0.5  # unusual volume (could be news-driven)
    if vol_ratio > 1.2:
        return 0.3  # above average
    if vol_ratio < 0.5:
        return -0.5  # shrinking
    if vol_ratio < 0.8:
        return -0.2  # slightly below average
    return 0.1


def analyst_score(df: pd.DataFrame) -> Dict[str, float]:
    """Aggregate all technical sub-scores for the latest row.

    Returns dict with overall score and breakdown.
    """
    trend = score_trend(df)
    momentum = score_momentum(df)
    vol = score_volatility(df)
    volume = score_volume(df)

    # Weighted composite
    overall = trend * 0.35 + momentum * 0.35 + vol * 0.15 + volume * 0.15

    return {
        "score": round(max(-1.0, min(1.0, overall)), 4),
        "trend": round(trend, 4),
        "momentum": round(momentum, 4),
        "volatility_risk": round(vol, 4),
        "volume_health": round(volume, 4),
    }
