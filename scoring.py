"""
Scoring engine.

A posting gets a 0-100 fit score built from four parts:

    skills      how much of the resume the posting actually asks for
    title       does the job title itself match a target track
    pay         does it clear the floor / hit the target
    sector      is the employer in a growing corner of the metro

Disqualifier phrases subtract. The track weight (direct / stretch / growth)
is applied last as a multiplier.

Pure standard library on purpose -- it runs anywhere and is easy to unit test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from job_profile import (
    SKILL_KEYWORDS,
    SECTOR_BONUS,
    DISQUALIFIERS,
    SEARCH_TRACKS,
    SALARY_FLOOR,
    SALARY_TARGET,
    SALARY_STRETCH,
    COL_INDEX,
)

# Titles that map straight onto the resume get a flat bump.
STRONG_TITLE_TOKENS = (
    "accounts receivable",
    "cash application",
    "billing",
    "finance associate",
    "banker",
    "branch operations",
    "will call",
    "aml",
    "bsa",
    "fraud",
    "kyc",
    "revenue cycle",
    "credit analyst",
    "operations analyst",
)

SENIOR_TITLE_TOKENS = ("director", "vp ", "vice president", "head of", "chief", "principal")


@dataclass
class Job:
    """One posting, normalized across every source."""
    source: str
    external_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    posted_at: Optional[str] = None
    metro: str = ""
    track: str = "direct"

    # filled in by score_job()
    score: float = 0.0
    reasons: list = field(default_factory=list)
    flags: list = field(default_factory=list)

    def key(self) -> str:
        """Stable identity for dedupe across sources (same job, two boards)."""
        norm = lambda s: re.sub(r"[^a-z0-9]+", "", (s or "").lower())
        return f"{norm(self.company)}:{norm(self.title)}:{norm(self.location)[:12]}"

    def to_dict(self) -> dict:
        return asdict(self)


def _haystack(job: Job) -> str:
    return f"{job.title}\n{job.company}\n{job.description}".lower()


def _salary_points(job: Job) -> tuple[float, list[str], list[str]]:
    """Pay is scored against the floor, not against the market."""
    reasons: list[str] = []
    flags: list[str] = []

    top = job.salary_max or job.salary_min
    if not top:
        # No posted salary is normal, not disqualifying. Neutral score.
        flags.append("no salary posted")
        return 6.0, reasons, flags

    # Adjust for cost of living so Albany dollars and Texas dollars compare.
    col = COL_INDEX.get(job.metro, 1.0)
    effective = top / col

    if effective >= SALARY_STRETCH:
        reasons.append(f"pay tops out near ${top:,.0f} — well above current")
        return 25.0, reasons, flags
    if effective >= SALARY_TARGET:
        reasons.append(f"pay clears the ${SALARY_TARGET:,} target (${top:,.0f})")
        return 18.0, reasons, flags
    if effective >= SALARY_FLOOR:
        reasons.append(f"pay is a lateral-to-modest step (${top:,.0f})")
        return 9.0, reasons, flags

    flags.append(f"below floor (${top:,.0f})")
    return -8.0, reasons, flags


def _skill_points(text: str) -> tuple[float, list[str]]:
    hits: list[tuple[str, int]] = []
    for kw, pts in SKILL_KEYWORDS.items():
        if kw in text:
            hits.append((kw, pts))

    if not hits:
        return 0.0, []

    hits.sort(key=lambda h: -h[1])
    # Diminishing returns: the 9th keyword does not tell you much the 3rd didn't.
    total = sum(pts * (0.85 ** i) for i, (_, pts) in enumerate(hits))
    top_named = ", ".join(kw for kw, _ in hits[:4])
    return min(total, 45.0), [f"matches your experience: {top_named}"]


def _title_points(title: str) -> tuple[float, list[str], list[str]]:
    t = title.lower()
    reasons: list[str] = []
    flags: list[str] = []
    pts = 0.0

    if any(tok in t for tok in STRONG_TITLE_TOKENS):
        pts += 14.0
        reasons.append("title is a direct match for your background")

    if any(tok in t for tok in SENIOR_TITLE_TOKENS):
        pts -= 12.0
        flags.append("senior title — likely out of range for now")

    if re.search(r"\b(sr\.?|senior)\b", t):
        pts -= 4.0

    if re.search(r"\b(i|entry|associate|jr\.?|junior)\b", t):
        pts += 3.0

    return pts, reasons, flags


def _sector_points(text: str) -> tuple[float, list[str]]:
    hits = [name for name in SECTOR_BONUS if name in text]
    if not hits:
        return 0.0, []
    pts = min(sum(SECTOR_BONUS[h] for h in hits), 14.0)
    return pts, [f"growing employer/sector in this metro: {hits[0]}"]


def _disqualifier_points(text: str) -> tuple[float, list[str]]:
    flags: list[str] = []
    pts = 0.0
    for phrase, penalty in DISQUALIFIERS.items():
        if phrase in text:
            pts += penalty
            flags.append(f"posting asks for: {phrase}")
    return pts, flags


def score_job(job: Job) -> Job:
    """Attach a 0-100 score plus human-readable reasons and flags."""
    text = _haystack(job)
    reasons: list[str] = []
    flags: list[str] = []
    total = 0.0

    pts, why = _skill_points(text)
    total += pts
    reasons += why

    pts, why, warn = _title_points(job.title)
    total += pts
    reasons += why
    flags += warn

    pts, why, warn = _salary_points(job)
    total += pts
    reasons += why
    flags += warn

    pts, why = _sector_points(text)
    total += pts
    reasons += why

    pts, warn = _disqualifier_points(text)
    total += pts
    flags += warn

    weight = SEARCH_TRACKS.get(job.track, {}).get("weight", 1.0)
    total *= weight

    job.score = max(0.0, min(100.0, round(total, 1)))
    job.reasons = reasons
    job.flags = flags
    return job


def rank(jobs: list[Job], minimum: float = 35.0) -> list[Job]:
    """Score, drop the noise, sort best first."""
    scored = [score_job(j) for j in jobs]
    keep = [j for j in scored if j.score >= minimum]
    keep.sort(key=lambda j: -j.score)
    return keep
