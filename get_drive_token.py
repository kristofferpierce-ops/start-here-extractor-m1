from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

Path("token.json").write_text(creds.to_json(), encoding="utf-8")
print("ACCESS_TOKEN:")
print(creds.token)
print("\nSaved refreshable credentials to token.json")