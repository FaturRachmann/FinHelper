import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

KEY = "config/google_credentials.json"
SPREADSHEET_ID = "1U_QczwOKkUPs89y4znRWHFufxt58Fb2dxMVfUNkuTuk"
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly",
          "https://www.googleapis.com/auth/drive"]

with open(KEY, "r", encoding="utf-8") as f:
    data = json.load(f)
print("client_email:", data.get("client_email"))

creds = Credentials.from_service_account_file(KEY, scopes=SCOPES)
drive = build("drive", "v3", credentials=creds)
try:
    perms = drive.permissions().list(fileId=SPREADSHEET_ID, fields="permissions(id,type,emailAddress,role)").execute()
    print("Permissions on file:")
    for p in perms.get("permissions", []):
        print(p)
except Exception as e:
    print("Permission check failed:", repr(e))