from __future__ import annotations

import os
import re
from typing import List
import base64
import html as html_lib
from urllib.parse import urlparse, urlunparse


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from job_agent.config import GMAIL_SCOPES
from job_agent.models import Job


def get_gmail_service():
    """Return an authenticated Gmail service client."""
    creds = None

    if os.path.exists("gmail_token.json"):
        creds = Credentials.from_authorized_user_file("gmail_token.json", GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "gmail_credentials.json",
                GMAIL_SCOPES,
            )
            creds = flow.run_local_server(port=0)

        with open("gmail_token.json", "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def fetch_messages(query: str, max_results: int = 15):
    service = get_gmail_service()
    response = (
        service.users()
        .messages()
        .list(
            userId="me",
            q=query,
            maxResults=max_results,
        )
        .execute()
    )
    return response.get("messages", [])

def extract_html_body(message: dict) -> str | None:
    """
    Invariant: parse the actual email body, not the snippet.
    Walk payload parts, find text/html, base64-decode, return HTML.
    """
    payload = message.get("payload", {})
    # Case: HTML is the top-level payload (no parts)
    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode(
                "utf-8", errors="ignore"
            )
    parts = payload.get("parts", [])

    for part in parts:
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data")
            if not data:
                continue
            decoded = base64.urlsafe_b64decode(data).decode(
                "utf-8", errors="ignore"
            )
            return decoded

    # Sometimes the HTML part is nested one level deeper
    for part in parts:
        for sub in part.get("parts", []) or []:
            if sub.get("mimeType") == "text/html":
                data = sub.get("body", {}).get("data")
                if not data:
                    continue
                decoded = base64.urlsafe_b64decode(data).decode(
                    "utf-8", errors="ignore"
                )
                return decoded

    return None


def _canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean)


def extract_job_urls_from_html(html: str) -> list[str]:
    """
    Invariant: extract canonical job posting URLs, not UI chrome.
    """
    hrefs = re.findall(r'href=["\'](.*?)["\']', html, flags=re.IGNORECASE)
    urls: list[str] = []

    for raw in hrefs:
        unescaped = html_lib.unescape(raw)

        if (
            "linkedin.com/jobs/view/" not in unescaped
            and "linkedin.com/comm/jobs/view/" not in unescaped
        ):
            continue


        clean = unescaped.split("?", 1)[0]

        urls.append(clean)

    # De-dupe, preserve order
    return list(dict.fromkeys(urls))

def extract_jobs_from_email(message_id: str, service) -> List[Job]:
    """Extract URL candidates from an email (currently from snippet only).

    This intentionally matches existing v0 behavior so refactors don't change outputs.
    """
    message = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="full",
        )
        .execute()
    )

    headers = {
        h["name"].lower(): h["value"]
        for h in message.get("payload", {}).get("headers", [])
    }

    subject = headers.get("subject", "")
    sender = headers.get("from", "")
    html = extract_html_body(message)
    if not html:
        return []

    urls = extract_job_urls_from_html(html)


    jobs: List[Job] = []
    for url in urls:
        jobs.append(
            Job(
                source="gmail",
                url=url,
                job_description=f"Subject: {subject}\nFrom: {sender}\nURL: {url}",
                metadata={
                    "email_subject": subject,
                    "email_sender": sender,
                },
            )
        )

    return jobs
