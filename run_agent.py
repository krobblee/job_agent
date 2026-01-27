from __future__ import annotations

import os

from agent.agent import rank_jobs
from agent.db import init_db
from agent.gmail_client import extract_jobs_from_email, fetch_messages, get_gmail_service


def main() -> None:
    init_db()

    query = os.getenv(
        "GMAIL_QUERY",
        'from:(jobalerts-noreply@linkedin.com) newer_than: 7d'
    )



    service = get_gmail_service()
    print("GMAIL_QUERY =", query)
    messages = fetch_messages(query)
    print(f"Fetched {len(messages)} messages")

    jobs = []
    for m in messages:
        jobs.extend(extract_jobs_from_email(m["id"], service))

    print(f"Extracted {len(jobs)} jobs from Gmail")
    for j in jobs[:5]:
        print(j.url)

    digest, raw = rank_jobs(jobs)

    print("---- MODEL OUTPUT START ----")
    print(raw)
    print("---- MODEL OUTPUT END ----")

    print("\n=== TOP MATCHES ===")
    for r in digest.top:
        print(f"\n[{r.score}] {r.url}")
        for reason in r.why:
            print(f"- {reason}")
        print(f"Next: {r.what_to_do_next}")


if __name__ == "__main__":
    main()
