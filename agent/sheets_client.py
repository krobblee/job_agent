from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class SheetConfig:
    sheet_id: str
    worksheet_title: str = "Sheet1"
    credentials_path: str = "credentials/service_account.json"


class SheetsClient:
    def __init__(self, cfg: SheetConfig):
        self.cfg = cfg
        creds = Credentials.from_service_account_file(cfg.credentials_path, scopes=SCOPES)
        self._client = gspread.authorize(creds)
        self._ws = self._client.open_by_key(cfg.sheet_id).worksheet(cfg.worksheet_title)

    @property
    def worksheet(self):
        return self._ws

    def get_header(self) -> List[str]:
        values = self._ws.get_all_values()
        return values[0] if values else []

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
