"""
JSearch adapter (RapidAPI).

JSearch indexes Google for Jobs, which means it reaches Indeed, LinkedIn,
Glassdoor and ZipRecruiter postings through a legitimate API instead of
scraping them. Free tier is roughly 200 requests/month -- enough for one
daily scan across a handful of queries, so keep QUERIES_PER_RUN modest.
"""

from __future__ import annotations

import logging
import os

import httpx

from job_profile import METROS
from scoring import Job

log = logging.getLogger(__name__)

BASE = "https://jsearch.p.rapidapi.com/search"
KEY = os.getenv("RAPIDAPI_KEY", "")


def available() -> bool:
    return bool(KEY)


def _annualize(pay: float | None, period: str | None) -> float | None:
    """Postings quote hourly, monthly or yearly. Normalize to yearly."""
    if not pay:
        return None
    p = (period or "").upper()
    if p == "HOUR":
        return pay * 2080
    if p == "WEEK":
        return pay * 52
    if p == "MONTH":
        return pay * 12
    return pay


def fetch(track: str, query: str, metro_key: str) -> list[Job]:
    if not available():
        log.warning("RAPIDAPI_KEY missing; skipping JSearch")
        return []

    metro = METROS[metro_key]
    params = {
        "query": f"{query} {metro['jsearch_query_suffix']}",
        "page": "1",
        "num_pages": "1",
        "date_posted": "week",
        "employment_types": "FULLTIME",
    }
    headers = {
        "X-RapidAPI-Key": KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }

    try:
        r = httpx.get(BASE, params=params, headers=headers, timeout=25)
        r.raise_for_status()
        payload = r.json()
    except Exception as e:  # noqa: BLE001
        log.error("JSearch fetch failed for %r/%s: %s", query, metro_key, e)
        return []

    jobs: list[Job] = []
    for item in payload.get("data", []):
        period = item.get("job_salary_period")
        city = item.get("job_city") or ""
        state = item.get("job_state") or ""
        jobs.append(
            Job(
                source="jsearch",
                external_id=str(item.get("job_id", "")),
                title=(item.get("job_title") or "").strip(),
                company=(item.get("employer_name") or "").strip(),
                location=", ".join(x for x in (city, state) if x),
                url=item.get("job_apply_link", "") or item.get("job_google_link", ""),
                description=(item.get("job_description") or "")[:6000],
                salary_min=_annualize(item.get("job_min_salary"), period),
                salary_max=_annualize(item.get("job_max_salary"), period),
                posted_at=item.get("job_posted_at_datetime_utc"),
                metro=metro_key,
                track=track,
            )
        )
    log.info("JSearch %s/%s -> %d results", metro_key, query, len(jobs))
    return jobs
