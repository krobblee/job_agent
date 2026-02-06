from __future__ import annotations

from typing import List, Union

from pydantic import BaseModel, Field


class Job(BaseModel):
    source: str  # "gmail", later "ashby", "greenhouse"
    url: str
    title: str | None = None
    company: str | None = None
    location_text: str | None = None
    salary_text: str | None = None
    employment_type: str | None = None
    job_description: str | None = None
    metadata: dict = {}


class ScoredJob(BaseModel):
    """
    Job scoring result with categorical bucket.
    
    Buckets:
    - true_match: Strong fit, apply immediately
    - monitor: Potential fit, keep watching
    - reject: Not a good fit
    """
    url: str
    bucket: str  # "true_match", "monitor", or "reject"
    why: List[str]  # Reasoning for the bucket decision
    what_to_do_next: str  # Action recommendation


class AgentDigest(BaseModel):
    """
    Complete scoring digest from agent.
    
    Contains all scored jobs organized by bucket.
    """
    true_matches: List[ScoredJob]  # Jobs to apply to immediately
    monitor: List[ScoredJob]  # Jobs to keep an eye on
    rejects: List[ScoredJob]  # Jobs to skip
    notes: Union[List[str], str]  # General observations/suggestions
