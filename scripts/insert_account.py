import sqlite3

DB = "finhelper.db"
MAPPING = {
    "cash": "CASH",
    "bank": "BANK",
    "e_wallet": "E_WALLET",
    "ewallet": "E_WALLET",
    "credit_card": "CREDIT_CARD",
    "creditcard": "CREDIT_CARD",
}

def distinct_types(cur):
    return [row[0] for row in cur.execute("SELECT DISTINCT account_type FROM accounts")]

con = sqlite3.connect(DB)
cur = con.cursor()

print("Before:", distinct_types(cur))

updated = 0
for old in distinct_types(cur):
    if old is None:
        continue
    key = old.lower()
    if key in MAPPING and old != MAPPING[key]:
        cur.execute("UPDATE accounts SET account_type = ? WHERE account_type = ?", (MAPPING[key], old))
        updated += cur.rowcount
    elif old not in MAPPING.values():
        print("Warning: unmapped account_type =", old)

con.commit()
print("Rows updated:", updated)
print("After:", distinct_types(cur))

con.close()