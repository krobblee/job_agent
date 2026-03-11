"""
Debug Email/Gmail discovery — see how many messages and URLs are found.

Run: python3 scripts/debug_linkedin_discovery.py
"""

import os

from agent.discovery import GmailDiscoverySource


def main():
    query = os.getenv("GMAIL_QUERY", "from:(jobalerts-noreply@linkedin.com) newer_than:3d")
    max_results = 50  # Increase to see more

    print(f"Query: {query}")
    print(f"Max results: {max_results}\n")

    discovery = GmailDiscoverySource(query=query, max_results=max_results)
    service = discovery._get_service()

    # Fetch message IDs only (lightweight)
    response = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    messages = response.get("messages", [])
    print(f"Gmail API returned {len(messages)} message(s)\n")

    if not messages:
        print("No messages found. Check:")
        print("  - GMAIL_QUERY in .env")
        print("  - Do you have LinkedIn job alert emails in the last 3 days?")
        return

    jobs = discovery.discover_jobs()
    urls = list(dict.fromkeys(j.url for j in jobs))
    print(f"Extracted {len(jobs)} job(s), {len(urls)} unique URL(s)\n")

    for i, job in enumerate(jobs[:10]):
        print(f"  {i+1}. {job.url[:80]}...")
    if len(jobs) > 10:
        print(f"  ... and {len(jobs) - 10} more")


if __name__ == "__main__":
    main()
