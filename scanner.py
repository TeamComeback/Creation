"""
Scan orchestration + the daily digest email.

One scan = every track x every query x every metro, across whichever sources
have credentials. Results are scored, deduped, stored, and the best unseen
ones go out in one email.

Budget note: Adzuna's free tier is about 1,000 calls a month, and every
(track, query, metro) combination is one call. With five tracks of ten
queries across four metros that's ~200 combinations -- far more than one
morning can afford. So the scan works from a fixed call budget instead:
CALLS_PER_RUN (default 24, ~720/month daily) combinations per run, taken
as a rotating window over the full list. The list is interleaved so every
window mixes tracks and metros, and the whole list is covered every
~9 days.
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

CALLS_PER_RUN = int(os.getenv("CALLS_PER_RUN", "24"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "35"))
DIGEST_MIN_SCORE = float(os.getenv("DIGEST_MIN_SCORE", "45"))
STALE_AFTER_DAYS = int(os.getenv("STALE_AFTER_DAYS", "14"))


def _all_searches() -> list[tuple[str, str, str]]:
    """Every (track, query, metro) combination, interleaved.

    Ordered query-index first, then track, then metro, so a contiguous
    window of any size draws from every track and every metro rather than
    spending a whole morning on one track in one city.
    """
    depth = max(len(cfg["queries"]) for cfg in SEARCH_TRACKS.values())
    combos = []
    for i in range(depth):
        for track, cfg in SEARCH_TRACKS.items():
            if i >= len(cfg["queries"]):
                continue
            for metro_key in METROS:
                combos.append((track, cfg["queries"][i], metro_key))
    return combos


def todays_searches(budget: int | None = None) -> list[tuple[str, str, str]]:
    """Today's window of the rotation, sized to the call budget."""
    budget = CALLS_PER_RUN if budget is None else budget
    combos = _all_searches()
    if budget >= len(combos):
        return combos
    start = (date.today().toordinal() * budget) % len(combos)
    doubled = combos + combos
    return doubled[start:start + budget]


def run_scan() -> dict:
    store.init_db()
    collected: list[Job] = []
    errors: list[str] = []

    # Say out loud which sources are off BEFORE the loop. The warning inside
    # each adapter's fetch() can never fire, because run_scan checks
    # available() first and skips the call -- so a missing API key used to
    # produce a silent "found: 0" with nothing in the logs to explain it.
    active = []
    for name, module in (("adzuna", adzuna), ("jsearch", jsearch)):
        if module.available():
            active.append(name)
        else:
            msg = f"{name}: no credentials configured, skipping"
            log.warning(msg)
            errors.append(msg)

    if not active:
        log.error("no job sources are configured — scan will return nothing")

    for track, q, metro_key in todays_searches():
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
    purged = store.purge_stale(STALE_AFTER_DAYS)
    store.log_scan("all", found, len(unique), new_count, "; ".join(errors))

    log.info(
        "scan complete: %d found, %d kept, %d new, %d purged (sources: %s)",
        found, len(unique), new_count, purged, ", ".join(active) or "none",
    )
    return {
        "found": found,
        "kept": len(unique),
        "new": new_count,
        "purged": purged,
        "sources": active,
    }


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
        {" &middot; ".join(m["label"].replace(", FL", "") for m in METROS.values())}
        &middot; {date.today():%B %d, %Y}
      </div>
      <table style="width:100%;border-collapse:collapse">{rows}</table>
      <p style="color:#999;font-size:11px;margin-top:20px">
        Ranked against your resume. Apply inside 48 hours where you can.
      </p>
    </body></html>"""

    msg = EmailMessage()
    msg["Subject"] = f"{len(jobs)} job matches — FL scan {date.today():%b %d}"
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
