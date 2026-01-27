from agent.sheets_client import SheetConfig, SheetsClient
from agent.fetch_runner import FetchConfig, run_fetch_once

SHEET_ID = "1mGVfJZuQzfIEtIbqnpxyh9UajHZ8b9JA77lXpR2hOgo"

def main():
    sheet = SheetsClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title="Sheet1"))
    attempted = run_fetch_once(sheet, FetchConfig())
    print("Attempted:", attempted)

if __name__ == "__main__":
    main()
