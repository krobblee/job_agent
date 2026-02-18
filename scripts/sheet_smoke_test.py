import gspread
from google.oauth2.service_account import Credentials

from config import SHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def main():
    creds = Credentials.from_service_account_file(
        "credentials/service_account.json",
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    ws = client.open_by_key(SHEET_ID).sheet1

    print("Worksheet title:", ws.title)
    values = ws.get_all_values()
    print("Rows (including header):", len(values))
    if values:
        print("Header:", values[0])

    rows = ws.get_all_records()
    print(f"Loaded {len(rows)} rows")
    if rows:
        print("First row keys:", list(rows[0].keys()))

if __name__ == "__main__":
    main()
