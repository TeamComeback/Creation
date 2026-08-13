"""
Adzuna adapter.

Adzuna aggregates a very large share of US postings and has a genuinely free
API tier (register at developer.adzuna.com -- you get an app_id and app_key).
Salary data is better here than almost anywhere else, which matters because
pay is a scored input, not a footnote.
"""

from __future__ import annotations

import logging
import os

import httpx

from job_profile import METROS
from scoring import Job

log = logging.getLogger(__name__)

BASE = "https://api.adzuna.com/v1/api/jobs/us/search/1"
APP_ID = os.getenv("ADZUNA_APP_ID", "")
APP_KEY = os.getenv("ADZUNA_APP_KEY", "")


def available() -> bool:
    return bool(APP_ID and APP_KEY)


def fetch(track: str, query: str, metro_key: str, max_days_old: int = 14) -> list[Job]:
    if not available():
        log.warning("Adzuna credentials missing; skipping")
        return []

    metro = METROS[metro_key]
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "what": query,
        "where": metro["adzuna_where"],
        "distance": metro["radius_km"],
        "results_per_page": 30,
        "max_days_old": max_days_old,
        "content-type": "application/json",
    }

    try:
        r = httpx.get(BASE, params=params, timeout=25)
        r.raise_for_status()
        payload = r.json()
    except Exception as e:  # noqa: BLE001 -- a dead source must not kill the scan
        log.error("Adzuna fetch failed for %r/%s: %s", query, metro_key, e)
        return []

    jobs: list[Job] = []
    for item in payload.get("results", []):
        jobs.append(
            Job(
                source="adzuna",
                external_id=str(item.get("id", "")),
                title=item.get("title", "").strip(),
                company=(item.get("company") or {}).get("display_name", "").strip(),
                location=(item.get("location") or {}).get("display_name", "").strip(),
                url=item.get("redirect_url", ""),
                description=item.get("description", ""),
                salary_min=item.get("salary_min"),
                salary_max=item.get("salary_max"),
                posted_at=item.get("created"),
                metro=metro_key,
                track=track,
            )
        )
    log.info("Adzuna %s/%s -> %d results", metro_key, query, len(jobs))
    return jobs
