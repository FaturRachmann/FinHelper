import json
KEY = "config/google_credentials.json"
with open(KEY, "r", encoding="utf-8") as f:
    data = json.load(f)
print("client_email:", data.get("client_email"))
print("spreadsheet id to use:", "1U_QczwOKkUPs89y4znRWHFufxt58Fb2dxMVfUNkuTuk")