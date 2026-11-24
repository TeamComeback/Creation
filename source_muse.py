"""
The Muse adapter: a second, free, no-key source for the job board.

The main scan path (Adzuna and JSearch) needs API keys and had one point of failure: when it stopped,
the board emptied. The Muse publishes a public jobs feed that needs no key, so one dead feed no longer
empties the board. It covers fewer employers than the aggregators and carries no salary, but it
filters by location, which is what this board needs (Tampa Bay first, then Jacksonville).

    https://www.themuse.com/api/public/jobs?location=Tampa%2C%20FL&page=1

Every failure is logged and returns an empty list: this source must never stop the other sources.
"""

from __future__ import annotations

import logging
import re

import httpx

from job_profile import METROS
from scoring import Job

log = logging.getLogger(__name__)

BASE = "https://www.themuse.com/api/public/jobs"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json"}   # the feed answered 403 to the default python client on Nov 24 2026
# The feed's location filter wants "City, ST" ("Tampa, FL"); "Tampa Bay, FL" answered 404 on Nov 24 2026.
PAGES = 2           # 20 postings a page; two pages per metro keeps this to a few calls a day


# Nov 24 2026: switched off. The public jobs endpoint answers 404 to every request shape (the dry run in
# Actions showed it, from GitHub as well as from the sandbox). Set True to try it again; the code is kept.
ENABLED = False


def available() -> bool:
    return ENABLED      # no key needed


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def parse(payload: dict, metro_key: str) -> list[Job]:
    """Turn one page of The Muse's response into Jobs. Pure function, so it can be tested without the network."""
    jobs: list[Job] = []
    for item in (payload or {}).get("results", []) or []:
        locs = [x.get("name", "") for x in (item.get("locations") or []) if isinstance(x, dict)]
        url = ((item.get("refs") or {}).get("landing_page")) or ""
        title = (item.get("name") or "").strip()
        if not title or not url:
            continue
        jobs.append(Job(
            source="themuse",
            external_id=str(item.get("id", "")),
            title=title,
            company=((item.get("company") or {}).get("name") or "").strip(),
            location="; ".join(l for l in locs if l) or METROS[metro_key]["label"],
            url=url,
            description=_text(item.get("contents", "")),
            posted_at=item.get("publication_date"),
            metro=metro_key,
            track="direct",
        ))
    return jobs


def fetch(metro_key: str) -> list[Job]:
    metro = METROS[metro_key]
    jobs: list[Job] = []
    for page in range(1, PAGES + 1):
        try:
            r = httpx.get(BASE, params={"location": metro["adzuna_where"], "page": page}, headers=HEADERS, timeout=25)
            r.raise_for_status()
            payload = r.json()
        except Exception as e:  # noqa: BLE001 -- a dead source must not kill the scan
            log.error("The Muse fetch failed for %s page %d: %s", metro_key, page, e)
            break
        jobs += parse(payload, metro_key)
        if page >= (payload.get("page_count") or 0):
            break
    log.info("The Muse %s -> %d results", metro_key, len(jobs))
    return jobs
