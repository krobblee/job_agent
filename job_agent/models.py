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


class RankedItem(BaseModel):
    url: str
    score: int = Field(ge=0, le=100)
    likely_job_posting: bool
    why: List[str]
    what_to_do_next: str


class AgentDigest(BaseModel):
    top: List[RankedItem]
    rejects: List[str]
    notes: Union[List[str], str]
