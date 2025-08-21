from google.oauth2.service_account import Credentials
import gspread, os

KEY = "config/google_credentials.json"
SPREADSHEET_ID = os.environ.get("GSHEET_ID", "1U_QczwOKkUPs89y4znRWHFufxt58Fb2dxMVfUNkuTuk")
scopes = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(KEY, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.worksheet(os.environ.get("GSHEET_TRANSACTIONS_SHEET", "Transactions"))
rows = ws.get_all_values()
print("Last 5 rows:")
for r in rows[-5:]:
    print(r)