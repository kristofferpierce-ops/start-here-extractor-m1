from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

creds = Credentials.from_authorized_user_file("token.json", SCOPES)

if not creds.valid and creds.expired and creds.refresh_token:
    creds.refresh(Request())

Path("token.json").write_text(creds.to_json(), encoding="utf-8")
print("ACCESS_TOKEN:")
print(creds.token)
