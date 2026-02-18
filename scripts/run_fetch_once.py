from agent.sheet_client import SheetConfig, SheetClient
from agent.fetch_manager import FetchConfig, FetchManager
from config import LINKEDIN_WORKSHEET, SHEET_ID


def main():
    sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title=LINKEDIN_WORKSHEET))
    fetch_manager = FetchManager(sheet, FetchConfig())
    attempted = fetch_manager.fetch_pending_jobs()
    print("Attempted:", attempted)

if __name__ == "__main__":
    main()
