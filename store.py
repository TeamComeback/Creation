"""
SQLite persistence.

Two things matter here:
  1. Never show the same job twice (dedupe on a normalized company+title+location key).
  2. Remember what you did about it -- new / saved / applied / dismissed.

SQLite is deliberate. This is a single-user tool; a Postgres add-on is a
monthly bill for no benefit. Point DB_PATH at a mounted disk on Render if you
want it to survive redeploys.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable

from scoring import Job

DB_PATH = os.getenv("DB_PATH", "jobscan.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    key         TEXT PRIMARY KEY,
    source      TEXT,
    external_id TEXT,
    title       TEXT NOT NULL,
    company     TEXT,
    location    TEXT,
    url         TEXT,
    description TEXT,
    salary_min  REAL,
    salary_max  REAL,
    posted_at   TEXT,
    metro       TEXT,
    track       TEXT,
    score       REAL,
    reasons     TEXT,
    flags       TEXT,
    status      TEXT DEFAULT 'new',
    first_seen  TEXT,
    last_seen   TEXT,
    notified    INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jobs_score  ON jobs(score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

CREATE TABLE IF NOT EXISTS scans (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    source     TEXT,
    found      INTEGER,
    kept       INTEGER,
    new_jobs   INTEGER,
    error      TEXT
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def upsert_jobs(jobs: Iterable[Job]) -> int:
    """Insert new postings, refresh last_seen on ones we already know. Returns new count."""
    new = 0
    now = _now()
    with conn() as c:
        for j in jobs:
            existing = c.execute("SELECT key FROM jobs WHERE key = ?", (j.key(),)).fetchone()
            if existing:
                c.execute(
                    "UPDATE jobs SET last_seen = ?, score = ?, salary_min = ?, salary_max = ? WHERE key = ?",
                    (now, j.score, j.salary_min, j.salary_max, j.key()),
                )
                continue

            c.execute(
                """INSERT INTO jobs (key, source, external_id, title, company, location, url,
                                     description, salary_min, salary_max, posted_at, metro, track,
                                     score, reasons, flags, status, first_seen, last_seen, notified)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'new',?,?,0)""",
                (
                    j.key(), j.source, j.external_id, j.title, j.company, j.location, j.url,
                    (j.description or "")[:4000], j.salary_min, j.salary_max, j.posted_at,
                    j.metro, j.track, j.score, json.dumps(j.reasons), json.dumps(j.flags),
                    now, now,
                ),
            )
            new += 1
    return new


def get_jobs(status: str | None = None, metro: str | None = None,
             track: str | None = None, limit: int = 200) -> list[dict]:
    q = "SELECT * FROM jobs WHERE 1=1"
    args: list = []
    if status:
        q += " AND status = ?"
        args.append(status)
    if metro:
        q += " AND metro = ?"
        args.append(metro)
    if track:
        q += " AND track = ?"
        args.append(track)
    q += " ORDER BY score DESC, last_seen DESC LIMIT ?"
    args.append(limit)

    with conn() as c:
        rows = c.execute(q, args).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        d["reasons"] = json.loads(d.get("reasons") or "[]")
        d["flags"] = json.loads(d.get("flags") or "[]")
        out.append(d)
    return out


def unnotified(min_score: float = 45.0) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM jobs WHERE notified = 0 AND score >= ? ORDER BY score DESC LIMIT 25",
            (min_score,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["reasons"] = json.loads(d.get("reasons") or "[]")
        d["flags"] = json.loads(d.get("flags") or "[]")
        out.append(d)
    return out


def mark_notified(keys: list[str]) -> None:
    if not keys:
        return
    with conn() as c:
        c.executemany("UPDATE jobs SET notified = 1 WHERE key = ?", [(k,) for k in keys])


def set_status(key: str, status: str) -> None:
    if status not in {"new", "saved", "applied", "dismissed"}:
        raise ValueError(f"bad status: {status}")
    with conn() as c:
        c.execute("UPDATE jobs SET status = ? WHERE key = ?", (status, key))


def log_scan(source: str, found: int, kept: int, new_jobs: int, error: str = "") -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO scans (started_at, source, found, kept, new_jobs, error) VALUES (?,?,?,?,?,?)",
            (_now(), source, found, kept, new_jobs, error),
        )


def stats() -> dict:
    with conn() as c:
        total = c.execute("SELECT COUNT(*) n FROM jobs").fetchone()["n"]
        by_status = {
            r["status"]: r["n"]
            for r in c.execute("SELECT status, COUNT(*) n FROM jobs GROUP BY status").fetchall()
        }
        last = c.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "total": total,
        "by_status": by_status,
        "last_scan": dict(last) if last else None,
    }
