from opinion_trading.core.monthly_training import load_training_history
from opinion_trading.core.evaluation import load_prices, evaluate_signals

signals = load_training_history('data/memory')
print('signals cols:', signals.columns.tolist())
print('len signals', len(signals))

price_df = load_prices('data/reports/price_history_template.csv')
print('price cols:', price_df.columns.tolist())

merged, summary = evaluate_signals(signals, price_df)
print('merged cols:', merged.columns.tolist())
print('merged head:')
print(merged.head().to_dict(orient='records'))
print('summary:', summary)
