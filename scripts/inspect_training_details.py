from opinion_trading.core.monthly_training import load_training_history

df = load_training_history("data/memory")
print("rows", len(df))
print("min", df["trade_date"].min())
print("max", df["trade_date"].max())
print("symbols", sorted(df["symbol"].dropna().unique()))
