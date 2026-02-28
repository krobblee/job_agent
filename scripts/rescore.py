"""
Rescore all fetched jobs and write results to the sheet.
Use when profile/rules changed (e.g. salary requirements) and you want
to update agent_bucket/agent_reasoning without re-fetching or discovery.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.scorer import rank_jobs
from agent.sheet_client import SheetClient, SheetConfig
from config import LINKEDIN_WORKSHEET, SHEET_ID
from models import Job


def _build_jobs_from_records(records: list) -> list[Job]:
    jobs = []
    for rec in records:
        if rec.get("fetch_status") == "fetched":
            job = Job(
                source=rec.get("source", "unknown"),
                url=rec.get("job_url", ""),
                title=rec.get("role_title"),
                company=rec.get("company"),
                location_text=rec.get("location"),
                job_description=rec.get("job_description"),
            )
            job.metadata["fetch_status"] = "fetched"
            jobs.append(job)
    return jobs


def main():
    sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title=LINKEDIN_WORKSHEET))
    sheet.refresh_worksheet()

    records = sheet.get_all_records()
    jobs = _build_jobs_from_records(records)

    if not jobs:
        print("No fetched jobs to rescore.")
        return

    print(f"Rescoring {len(jobs)} jobs...")
    digest, _ = rank_jobs(jobs)

    all_scored = digest.true_matches + digest.monitor + digest.rejects
    updated = sheet.write_scoring_results(all_scored)
    print(f"✓ Updated {updated} jobs with new scores")


if __name__ == "__main__":
    main()
