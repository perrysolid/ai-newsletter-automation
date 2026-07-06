"""
One-time helper: generates GOOGLE_REFRESH_TOKEN for the newsletter MCP server.

Usage:
  1. Put GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env (OAuth "Desktop app" client)
  2. Run: .venv/bin/python get_refresh_token.py
  3. A browser opens — log in and approve access
  4. Copy the printed refresh token into .env
"""

import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

load_dotenv()
client_id = os.getenv("GOOGLE_CLIENT_ID")
client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

if not client_id or not client_secret:
    raise SystemExit("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env first.")

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    },
    scopes=SCOPES,
)

creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

print("\n" + "=" * 60)
print("Add this line to your .env file:")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
print("=" * 60)
