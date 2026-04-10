import os
from dotenv import load_dotenv
load_dotenv()

SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

try:
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    print(f"✅ Connected: {sh.title}")
    print(f"✅ Google Sheets is working!")

except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")