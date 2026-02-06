from agent.sheet_client import SheetConfig, SheetClient
from agent.fetch_manager import FetchConfig, FetchManager

SHEET_ID = "1mGVfJZuQzfIEtIbqnpxyh9UajHZ8b9JA77lXpR2hOgo"

def main():
    sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title="Sheet1"))
    fetch_manager = FetchManager(sheet, FetchConfig())
    attempted = fetch_manager.fetch_pending_jobs()
    print("Attempted:", attempted)

if __name__ == "__main__":
    main()
