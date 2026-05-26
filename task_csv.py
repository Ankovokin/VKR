import pandas as pd

# Загружаем файл
df = pd.read_excel("synthetic_cheki_5000_utf8 (1).xlsx", sheet_name="synthetic_cheki_5000_utf8 (2)")

# Распаковываем товары
df_unpacked = (
    df[['transaction_id', 'items']]
    .dropna()
    .assign(items=df['items'].str.split(';'))
    .explode('items')
    .rename(columns={'items': 'item'})
)
df_unpacked['item'] = df_unpacked['item'].str.strip()

# Сохраняем результат
df_unpacked.to_csv("unpacked_cheki.csv", index=False, encoding="utf-8")


print("✅ Готово! Файл 'unpacked_cheki.csv' создан.")