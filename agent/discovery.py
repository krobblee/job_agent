from __future__ import annotations

import base64
import html as html_lib
import os
import re
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import GMAIL_SCOPES
from models import Job


class GmailDiscoverySource:
    """
    Discovers job postings from Gmail alerts.
    
    Authenticates with Gmail API, queries for messages, extracts job URLs,
    and returns structured Job objects.
    """
    
    def __init__(self, query: str, max_results: int = 15):
        """
        Args:
            query: Gmail search query (e.g., 'from:(jobalerts-noreply@linkedin.com)')
            max_results: Maximum number of messages to fetch
        """
        self.query = query
        self.max_results = max_results
        self._service = None
    
    def _get_service(self):
        """Return an authenticated Gmail service client."""
        if self._service is not None:
            return self._service
        
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
        
        self._service = build("gmail", "v1", credentials=creds)
        return self._service
    
    def _fetch_messages(self) -> List[dict]:
        """Fetch messages matching the query."""
        service = self._get_service()
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=self.query,
                maxResults=self.max_results,
            )
            .execute()
        )
        return response.get("messages", [])
    
    def _extract_html_body(self, message: dict) -> str | None:
        """
        Extract HTML body from Gmail message.
        
        Invariant: parse the actual email body, not the snippet.
        Walk payload parts, find text/html, base64-decode, return HTML.
        """
        payload = message.get("payload", {})
        
        # Case: HTML is the top-level payload (no parts)
        if payload.get("mimeType") == "text/html":
            data = payload.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        
        parts = payload.get("parts", [])
        
        for part in parts:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data")
                if not data:
                    continue
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        
        # Sometimes the HTML part is nested one level deeper
        for part in parts:
            for sub in part.get("parts", []) or []:
                if sub.get("mimeType") == "text/html":
                    data = sub.get("body", {}).get("data")
                    if not data:
                        continue
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        
        return None
    
    def _extract_job_urls_from_html(self, html: str) -> List[str]:
        """
        Extract canonical job posting URLs from HTML.
        
        Invariant: extract canonical job posting URLs, not UI chrome.
        Normalizes URLs by removing /comm/ path which triggers stricter anti-scraping.
        """
        hrefs = re.findall(r'href=["\'](.*?)["\']', html, flags=re.IGNORECASE)
        urls: List[str] = []
        
        for raw in hrefs:
            unescaped = html_lib.unescape(raw)
            
            if (
                "linkedin.com/jobs/view/" not in unescaped
                and "linkedin.com/comm/jobs/view/" not in unescaped
            ):
                continue
            
            # Remove query params for canonical URL
            clean = unescaped.split("?", 1)[0]
            
            # Normalize: strip /comm/ from email tracking URLs
            # linkedin.com/comm/jobs/view/123 -> linkedin.com/jobs/view/123
            clean = clean.replace("/comm/jobs/view/", "/jobs/view/")
            
            urls.append(clean)
        
        # De-dupe, preserve order
        return list(dict.fromkeys(urls))
    
    def _extract_jobs_from_message(self, message_id: str) -> List[Job]:
        """Extract Job objects from a single Gmail message."""
        service = self._get_service()
        
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
        html = self._extract_html_body(message)
        
        if not html:
            return []
        
        urls = self._extract_job_urls_from_html(html)
        
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
    
    def discover_jobs(self) -> List[Job]:
        """
        Main discovery method: fetch messages and extract all job URLs.
        
        Returns:
            List of Job objects discovered from Gmail
        """
        messages = self._fetch_messages()
        
        all_jobs: List[Job] = []
        for msg in messages:
            jobs = self._extract_jobs_from_message(msg["id"])
            all_jobs.extend(jobs)
        
        return all_jobs
