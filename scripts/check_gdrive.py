import json, os, sys, logging
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)

KEY_PATH = "config/google_credentials.json"
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly",
          "https://www.googleapis.com/auth/drive"]

if not os.path.exists(KEY_PATH):
    print("KEY NOT FOUND:", KEY_PATH); sys.exit(1)

with open(KEY_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
print("client_email:", data.get("client_email"))
print("project_id:", data.get("project_id"))

try:
    creds = Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
    # lightweight Drive API call to get storage quota via about.get
    from googleapiclient.discovery import build
    drive = build("drive", "v3", credentials=creds)
    about = drive.about().get(fields="user,storageQuota").execute()
    print("Drive user:", about.get("user"))
    print("storageQuota:", about.get("storageQuota"))
    # list a few files (metadata)
    files = drive.files().list(pageSize=5, fields="files(id,name,owners)").execute()
    print("files sample:", files.get("files"))
except Exception as e:
    logging.exception("Drive API call failed")
    print("Exception:", repr(e))