"""
Rescore Company Jobs with updated agent_bucket/agent_reasoning.
Use when profile/rules changed or after scorer prompt improvements.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.scorer import rank_jobs
from agent.sheet_client import SheetClient, SheetConfig
from config import COMPANIES_JOBS_WORKSHEET, SHEET_ID
from models import Job
from scripts.prune_company_jobs_rejects import prune_rejected_company_job_rows


def _build_jobs_from_records(records: list) -> list[Job]:
    jobs = []
    for rec in records:
        if rec.get("fetch_status") == "fetched":
            job = Job(
                source=rec.get("source", "companies"),
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
    sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title=COMPANIES_JOBS_WORKSHEET))
    sheet.refresh_worksheet()

    records = sheet.get_all_records()
    jobs = _build_jobs_from_records(records)

    if not jobs:
        print("No fetched jobs to rescore.")
        return

    print(f"Rescoring {len(jobs)} Company Jobs...")
    digest, _ = rank_jobs(jobs)

    all_scored = digest.true_matches + digest.monitor + digest.rejects
    updated = sheet.write_scoring_results(all_scored)
    print(f"✓ Updated {updated} jobs with new scores")

    sheet.refresh_worksheet()
    pruned = prune_rejected_company_job_rows(sheet)
    if pruned:
        print(f"✓ Removed {pruned} rejected row(s) from Company Jobs")


if __name__ == "__main__":
    main()
