import sqlite3

DB = "finhelper.db"

TRANSACTION_TYPE_MAP = {
    "income": "INCOME",
    "expense": "EXPENSE",
    "transfer": "TRANSFER",
}
SOURCE_MAP = {
    "manual": "MANUAL",
    "csv_import": "CSV_IMPORT",
    "csv-import": "CSV_IMPORT",
    "csv": "CSV_IMPORT",
    "telegram_bot": "TELEGRAM_BOT",
    "telegram": "TELEGRAM_BOT",
}

con = sqlite3.connect(DB)
cur = con.cursor()

def normalize_column(table, column, mapping):
    cur.execute(f"SELECT DISTINCT {column} FROM {table}")
    rows = [r[0] for r in cur.fetchall()]
    updated = 0
    for v in rows:
        if v is None:
            continue
        key = str(v).strip().lower()
        if key in mapping and v != mapping[key]:
            cur.execute(f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (mapping[key], v))
            updated += cur.rowcount
    return updated

u1 = normalize_column("accounts", "account_type", {k: v for k, v in TRANSACTION_TYPE_MAP.items()})  # harmless if no match
u2 = normalize_column("transactions", "transaction_type", TRANSACTION_TYPE_MAP)
u3 = normalize_column("transactions", "source", SOURCE_MAP)

con.commit()
print("updated account_type rows:", u1)
print("updated transaction_type rows:", u2)
print("updated source rows:", u3)
con.close()