"""情感与价格相关性分析 + 格兰杰因果检验脚本

用法示例：
  python scripts/correlation_granger.py --sentiment data/memory/sentiment_history.jsonl --prices data/reports/price_history_cache.csv --symbol 000001.SZ

输出：控制台与 CSV 报表（correlation_results_<symbol>.csv）

依赖：pandas, numpy, scipy, statsmodels
"""
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.stats import pearsonr, spearmanr
from statsmodels.tsa.stattools import grangercausalitytests


def load_sentiment(path: Path, symbol: str = None) -> pd.DataFrame:
    df = pd.read_json(path, lines=True)
    df['trade_date'] = pd.to_datetime(df['trade_date'], errors='coerce')
    if symbol:
        df = df[df['symbol'] == symbol]
    return df


def load_prices(path: Path, symbol: str = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'], errors='coerce')
    if symbol:
        df = df[df['symbol'] == symbol]
    return df


def aggregate_daily_sentiment(sent_df: pd.DataFrame) -> pd.DataFrame:
    # daily mean sentiment per symbol
    s = (
        sent_df.dropna(subset=['trade_date', 'sentiment_score'])
        .groupby(['symbol', pd.Grouper(key='trade_date', freq='D')])
        .agg(sentiment_mean=('sentiment_score', 'mean'), samples=('sentiment_score','count'))
        .reset_index()
    )
    return s


def compute_future_returns(price_df: pd.DataFrame, horizons=[1,3,5,7]) -> pd.DataFrame:
    price_df = price_df.sort_values('trade_date')
    price_df = price_df.set_index('trade_date')
    out = price_df[['close']].copy()
    for h in horizons:
        out[f'ret_{h}d'] = out['close'].shift(-h) / out['close'] - 1
    out = out.reset_index()
    return out


def run_correlation(sent_daily: pd.DataFrame, price_df: pd.DataFrame, symbol: str, horizons=[1,3,5,7]):
    # merge and compute correlations
    price_symbol = price_df[price_df['symbol'] == symbol].copy()
    if price_symbol.empty:
        print('No price data for', symbol)
        return
    price_sym = compute_future_returns(price_symbol, horizons=horizons)
    sent_sym = sent_daily[sent_daily['symbol'] == symbol].copy()
    merged = sent_sym.merge(price_sym[['trade_date'] + [f'ret_{h}d' for h in horizons]], on='trade_date', how='inner')
    if merged.empty:
        print('No merged rows for symbol', symbol)
        return
    rows = []
    for h in horizons:
        x = merged['sentiment_mean'].values
        y = merged[f'ret_{h}d'].values
        # drop nan
        mask = ~np.isnan(x) & ~np.isnan(y)
        if mask.sum() < 5:
            rows.append({'horizon': h, 'pearson_r': np.nan, 'pearson_p': np.nan, 'spearman_r': np.nan, 'spearman_p': np.nan})
            continue
        pr, pp = pearsonr(x[mask], y[mask])
        sr, sp = spearmanr(x[mask], y[mask])
        rows.append({'horizon': h, 'pearson_r': pr, 'pearson_p': pp, 'spearman_r': sr, 'spearman_p': sp, 'n': int(mask.sum())})
    out_df = pd.DataFrame(rows)
    out_csv = Path(f'correlation_results_{symbol.replace("/","_")}.csv')
    out_df.to_csv(out_csv, index=False)
    print('Wrote', out_csv)
    # Granger causality test on aggregated series
    print('\nGranger causality tests (sentiment -> ret_1d)')
    # prepare series
    gc_df = merged[['trade_date', 'sentiment_mean', 'ret_1d']].dropna()
    if len(gc_df) < 20:
        print('Too few rows for Granger tests')
        return
    test_df = gc_df[['ret_1d', 'sentiment_mean']]
    # statsmodels expects 2D array with [y, x]
    maxlag = min(7, int(len(test_df)/4))
    try:
        res = grangercausalitytests(test_df, maxlag=maxlag, verbose=False)
        print('Granger test completed up to lag', maxlag)
    except Exception as e:
        print('Granger test failed:', e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sentiment', type=str, default='data/memory/sentiment_history.jsonl')
    parser.add_argument('--prices', type=str, default='data/reports/price_history_cache.csv')
    parser.add_argument('--symbol', type=str, required=True)
    args = parser.parse_args()

    sent = load_sentiment(Path(args.sentiment), symbol=args.symbol)
    prices = load_prices(Path(args.prices), symbol=args.symbol)
    sent_daily = aggregate_daily_sentiment(sent)
    run_correlation(sent_daily, prices, args.symbol)


if __name__ == '__main__':
    main()
