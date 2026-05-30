from opinion_trading.core.monthly_training import load_training_history

df = load_training_history('data/memory')
print('empty:', df.empty)
print(df.dtypes)
print(df.head().to_dict(orient='records'))
