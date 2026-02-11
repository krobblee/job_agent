from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def utc_now_iso() -> str:
    """Return current time in Eastern Time (EST/EDT) with readable format."""
    eastern = ZoneInfo("America/New_York")
    now = datetime.now(eastern)
    # Format: "2026-02-05 13:09:55 EST" (or EDT during daylight saving)
    timezone_abbr = now.strftime("%Z")  # EST or EDT
    return now.strftime(f"%Y-%m-%d %H:%M:%S {timezone_abbr}")


@dataclass(frozen=True)
class SheetConfig:
    sheet_id: str
    worksheet_title: str = "Sheet1"
    credentials_path: str = "credentials/service_account.json"


class SheetClient:
    def __init__(self, cfg: SheetConfig):
        self.cfg = cfg
        creds = Credentials.from_service_account_file(cfg.credentials_path, scopes=SCOPES)
        self._client = gspread.authorize(creds)
        self._ws = self._client.open_by_key(cfg.sheet_id).worksheet(cfg.worksheet_title)
        self._header_cache: List[str] | None = None

    @property
    def worksheet(self):
        return self._ws
    
    def refresh_worksheet(self) -> None:
        """Force reload worksheet to clear any caching."""
        self._ws = self._client.open_by_key(self.cfg.sheet_id).worksheet(self.cfg.worksheet_title)
        self._header_cache = None

    def get_header(self, use_cache: bool = True) -> List[str]:
        """Get header row. use_cache=True to avoid redundant API calls."""
        if use_cache and self._header_cache is not None:
            return self._header_cache
        
        values = self._ws.get_all_values()
        header = values[0] if values else []
        self._header_cache = header
        return header

    def get_all_records(self) -> List[Dict[str, Any]]:
        return self._ws.get_all_records()

    def get_all_values(self) -> List[List[str]]:
        return self._ws.get_all_values()

    def build_row_index(self, key_col: str = "job_url") -> Dict[str, int]:
        """
        Returns mapping key -> 1-based row number in the sheet (including header row).
        Row 1 is header, so first data row is 2.
        """
        header = self.get_header()
        if not header:
            return {}

        if key_col not in header:
            raise ValueError(f"Missing required column in sheet header: {key_col}")

        key_idx = header.index(key_col)
        values = self.get_all_values()

        index: Dict[str, int] = {}
        for row_num, row in enumerate(values[1:], start=2):
            if key_idx >= len(row):
                continue
            key = (row[key_idx] or "").strip()
            if key:
                index[key] = row_num
        return index

    def append_row_dict(self, row: Dict[str, Any]) -> None:
        header = self.get_header()
        if not header:
            raise ValueError("Sheet header row is empty; cannot append.")

        out = []
        for col in header:
            val = row.get(col, "")
            out.append("" if val is None else str(val))
        self._ws.append_row(out, value_input_option="RAW")

    def update_row_cells(self, row_number: int, updates: Dict[str, Any]) -> None:
        header = self.get_header()
        if not header:
            raise ValueError("Sheet header row is empty; cannot update.")

        cell_updates = []
        for col, val in updates.items():
            if col not in header:
                raise ValueError(f"Column not found in sheet header: {col}")
            col_idx = header.index(col) + 1  # 1-based
            cell_updates.append(gspread.Cell(row_number, col_idx, "" if val is None else str(val)))

        if cell_updates:
            self._ws.update_cells(cell_updates, value_input_option="RAW")

    def batch_update_rows(self, row_updates: Dict[int, Dict[str, Any]]) -> None:
        """
        Batch update multiple rows at once to avoid rate limits.
        
        Args:
            row_updates: Dict mapping row_number -> {column: value}
        """
        if not row_updates:
            return
        
        header = self.get_header()
        if not header:
            raise ValueError("Sheet header row is empty; cannot update.")

        # Collect all cell updates across all rows
        all_cell_updates = []
        for row_num, updates in row_updates.items():
            for col, val in updates.items():
                if col not in header:
                    raise ValueError(f"Column not found in sheet header: {col}")
                col_idx = header.index(col) + 1  # 1-based
                all_cell_updates.append(gspread.Cell(row_num, col_idx, "" if val is None else str(val)))

        # Single batch update for all cells
        if all_cell_updates:
            try:
                print(f"    batch_update_rows: Updating {len(all_cell_updates)} cells across {len(row_updates)} rows")
                self._ws.update_cells(all_cell_updates, value_input_option="RAW")
                print(f"    batch_update_rows: ✓ Update successful")
            except Exception as e:
                print(f"    batch_update_rows: ✗ ERROR: {type(e).__name__}: {e}")
                raise
    
    def write_scoring_results(self, scored_jobs: List[Any]) -> int:
        """
        Write scoring results (bucket + reasoning) to Sheet.
        
        Args:
            scored_jobs: List of ScoredJob objects with url, bucket, why fields
            
        Returns:
            Number of jobs updated
        """
        if not scored_jobs:
            return 0
        
        # Build URL -> row mapping
        row_index = self.build_row_index(key_col="job_url")
        
        # Collect batch updates
        batch_updates: Dict[int, Dict[str, Any]] = {}
        
        for job in scored_jobs:
            row_num = row_index.get(job.url)
            if not row_num:
                continue  # URL not in sheet, skip
            
            # Format reasoning as bullet points
            reasoning = "\n".join(f"• {reason}" for reason in job.why)
            
            batch_updates[row_num] = {
                "agent_bucket": job.bucket,
                "agent_reasoning": reasoning,
            }
        
        # Write all updates at once
        if batch_updates:
            self.batch_update_rows(batch_updates)
        
        return len(batch_updates)
