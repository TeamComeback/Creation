"""
Direct-from-employer adapters.

Aggregators lag. Company applicant-tracking systems do not -- a Greenhouse or
Lever board shows a role the hour it opens, and applying inside the first 48
hours is measurably the difference between being read and being #400 in a pile.
Both expose public JSON with no key and no rate limit worth worrying about:

    https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
    https://api.lever.co/v0/postings/{slug}?mode=json

Slugs must be verified by opening the URL in a browser once -- they are the
company's own chosen handle and are not guessable with confidence. Anything
that 404s is logged and skipped, so a wrong slug costs you nothing but a line
in the log.

Big Texas employers on Workday (USAA, Frost, H-E-B) are not covered here;
Workday's endpoints are per-tenant and change. Use their careers pages plus
an email alert for those, or add a Workday adapter later.
"""

from __future__ import annotations

import logging

import httpx

from scoring import Job

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VERIFY THESE SLUGS before trusting the results. Open the URL in the docstring
# above with the slug substituted; if you get JSON, it's good. Delete what 404s.
# ---------------------------------------------------------------------------
COMPANY_BOARDS = {
    "greenhouse": [
     
    ],
}

TX_HINTS = ("san antonio", "dallas", "fort worth", "plano", "irving", "texas", ", tx")


def _is_target_location(text: str) -> bool:
    t = (text or "").lower()
    return any(h in t for h in TX_HINTS)


def _metro_of(text: str) -> str:
    t = (text or "").lower()
    if "san antonio" in t:
        return "san_antonio"
    return "dallas"


def fetch_greenhouse(slug: str, track: str = "direct") -> list[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        r = httpx.get(url, params={"content": "true"}, timeout=25)
        r.raise_for_status()
        payload = r.json()
    except Exception as e:  # noqa: BLE001
        log.error("Greenhouse board %s failed: %s", slug, e)
        return []

    jobs: list[Job] = []
    for item in payload.get("jobs", []):
        loc = (item.get("location") or {}).get("name", "")
        if not _is_target_location(loc):
            continue
        jobs.append(
            Job(
                source=f"greenhouse:{slug}",
                external_id=str(item.get("id", "")),
                title=(item.get("title") or "").strip(),
                company=slug.replace("-", " ").title(),
                location=loc,
                url=item.get("absolute_url", ""),
                description=(item.get("content") or "")[:6000],
                posted_at=item.get("updated_at"),
                metro=_metro_of(loc),
                track=track,
            )
        )
    log.info("Greenhouse %s -> %d TX results", slug, len(jobs))
    return jobs


def fetch_lever(slug: str, track: str = "direct") -> list[Job]:
    url = f"https://api.lever.co/v0/postings/{slug}"
    try:
        r = httpx.get(url, params={"mode": "json"}, timeout=25)
        r.raise_for_status()
        payload = r.json()
    except Exception as e:  # noqa: BLE001
        log.error("Lever board %s failed: %s", slug, e)
        return []

    jobs: list[Job] = []
    for item in payload:
        loc = ((item.get("categories") or {}).get("location")) or ""
        if not _is_target_location(loc):
            continue
        jobs.append(
            Job(
                source=f"lever:{slug}",
                external_id=str(item.get("id", "")),
                title=(item.get("text") or "").strip(),
                company=slug.replace("-", " ").title(),
                location=loc,
                url=item.get("hostedUrl", ""),
                description=(item.get("descriptionPlain") or "")[:6000],
                posted_at=str(item.get("createdAt", "")),
                metro=_metro_of(loc),
                track=track,
            )
        )
    log.info("Lever %s -> %d TX results", slug, len(jobs))
    return jobs
