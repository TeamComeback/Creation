"""
Scan orchestration + the daily digest email.

One scan = every track x every query x every metro, across whichever sources
have credentials. Results are scored, deduped, stored, and the best unseen
ones go out in one email.

Budget note: free API tiers are small. QUERIES_PER_RUN rotates through the
query list so a week of daily scans covers everything without burning quota
in a single morning.
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import date
from email.message import EmailMessage

import store
from job_profile import METROS, SEARCH_TRACKS
from scoring import Job, rank
import source_adzuna as adzuna, source_jsearch as jsearch
from source_boards import COMPANY_BOARDS, fetch_greenhouse, fetch_lever

log = logging.getLogger(__name__)

QUERIES_PER_RUN = int(os.getenv("QUERIES_PER_RUN", "4"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "35"))
DIGEST_MIN_SCORE = float(os.getenv("DIGEST_MIN_SCORE", "45"))


def _rotating_slice(items: list[str], n: int) -> list[str]:
    """Pick n queries, rotating by day-of-year so coverage is even over a week."""
    if n >= len(items):
        return items
    start = (date.today().timetuple().tm_yday * n) % len(items)
    doubled = items + items
    return doubled[start:start + n]


def run_scan() -> dict:
    store.init_db()
    collected: list[Job] = []
    errors: list[str] = []

    for track, cfg in SEARCH_TRACKS.items():
        queries = _rotating_slice(cfg["queries"], QUERIES_PER_RUN)
        for metro_key in METROS:
            for q in queries:
                if adzuna.available():
                    collected += adzuna.fetch(track, q, metro_key)
                if jsearch.available():
                    collected += jsearch.fetch(track, q, metro_key)

    for slug in COMPANY_BOARDS.get("greenhouse", []):
        collected += fetch_greenhouse(slug)
    for slug in COMPANY_BOARDS.get("lever", []):
        collected += fetch_lever(slug)

    found = len(collected)
    keepers = rank(collected, minimum=MIN_SCORE)

    # Dedupe within this run (same job from two sources) before hitting the DB.
    seen: set[str] = set()
    unique: list[Job] = []
    for j in keepers:
        if j.key() in seen:
            continue
        seen.add(j.key())
        unique.append(j)

    new_count = store.upsert_jobs(unique)
    store.log_scan("all", found, len(unique), new_count, "; ".join(errors))

    log.info("scan complete: %d found, %d kept, %d new", found, len(unique), new_count)
    return {"found": found, "kept": len(unique), "new": new_count}


# ---------------------------------------------------------------------------
# Digest
# ---------------------------------------------------------------------------

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")          # Gmail: use an App Password
DIGEST_TO = os.getenv("DIGEST_TO", "")


def _row_html(j: dict) -> str:
    sal = ""
    if j.get("salary_max"):
        sal = f"<div style='color:#2e7d32;font-size:13px'>${j['salary_max']:,.0f} max</div>"
    elif j.get("salary_min"):
        sal = f"<div style='color:#2e7d32;font-size:13px'>from ${j['salary_min']:,.0f}</div>"

    reasons = "".join(
        f"<li style='font-size:12px;color:#444'>{r}</li>" for r in (j.get("reasons") or [])[:3]
    )
    flags = "".join(
        f"<li style='font-size:12px;color:#b26500'>{f}</li>" for f in (j.get("flags") or [])[:2]
    )

    return f"""
    <tr><td style="padding:12px 0;border-bottom:1px solid #eee">
      <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px">
        {j['track']} &middot; {j['metro'].replace('_',' ')} &middot; score {j['score']:.0f}
      </div>
      <a href="{j['url']}" style="font-size:16px;font-weight:600;color:#1f3864;text-decoration:none">
        {j['title']}
      </a>
      <div style="font-size:13px;color:#333">{j['company']} &mdash; {j['location']}</div>
      {sal}
      <ul style="margin:6px 0 0 16px;padding:0">{reasons}{flags}</ul>
    </td></tr>"""


def send_digest() -> dict:
    jobs = store.unnotified(min_score=DIGEST_MIN_SCORE)
    if not jobs:
        return {"sent": 0, "reason": "nothing new above threshold"}
    if not (SMTP_USER and SMTP_PASS and DIGEST_TO):
        return {"sent": 0, "reason": "SMTP not configured"}

    rows = "".join(_row_html(j) for j in jobs)
    html = f"""
    <html><body style="font-family:-apple-system,Segoe UI,Helvetica,sans-serif;
                       max-width:640px;margin:0 auto;padding:16px">
      <h2 style="color:#1f3864;margin-bottom:4px">{len(jobs)} new matches</h2>
      <div style="color:#666;font-size:13px;margin-bottom:16px">
        San Antonio &amp; Dallas &middot; {date.today():%B %d, %Y}
      </div>
      <table style="width:100%;border-collapse:collapse">{rows}</table>
      <p style="color:#999;font-size:11px;margin-top:20px">
        Ranked against your resume. Apply inside 48 hours where you can.
      </p>
    </body></html>"""

    msg = EmailMessage()
    msg["Subject"] = f"{len(jobs)} job matches — TX scan {date.today():%b %d}"
    msg["From"] = SMTP_USER
    msg["To"] = DIGEST_TO
    msg.set_content(
        "\n\n".join(f"{j['title']} — {j['company']} ({j['location']})\n{j['url']}" for j in jobs)
    )
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

    store.mark_notified([j["key"] for j in jobs])
    return {"sent": len(jobs)}
