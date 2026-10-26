"""
Durable job snapshot.

Render's free tier keeps SQLite in /tmp, which is wiped every time the
service sleeps or redeploys. This file closes that gap without any new
account or secret:

  * A GitHub Action (.github/workflows/snapshot.yml) pulls /api/jobs from the
    live board every few hours and merges it into data/jobs.json in this repo.
  * On startup the app reads that file back (from raw.githubusercontent.com,
    the repo is public) and re-imports every job, keeping saved/applied/
    dismissed status.

Run as a script to merge a fresh pull into the snapshot:
    python snapshot.py <live.json> data/jobs.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

KEEP_DAYS = 14          # same window as store.purge_stale
STATUS_RANK = {"new": 0, "dismissed": 1, "saved": 2, "applied": 3}


def _ts(s: str | None) -> str:
    return s or ""


def merge(old: list[dict], live: list[dict]) -> list[dict]:
    """Union by key. Newer last_seen wins for job fields; the most advanced status wins."""
    by_key: dict[str, dict] = {r["key"]: r for r in old if r.get("key")}
    for r in live:
        k = r.get("key")
        if not k:
            continue
        prev = by_key.get(k)
        if prev is None:
            by_key[k] = r
            continue
        newer = r if _ts(r.get("last_seen")) >= _ts(prev.get("last_seen")) else prev
        merged = dict(newer)
        # A status set on the board is the user's record: never step it back to 'new'.
        s_new, s_old = r.get("status", "new"), prev.get("status", "new")
        merged["status"] = s_new if s_new != "new" else s_old
        merged["first_seen"] = min(_ts(prev.get("first_seen")) or "9", _ts(r.get("first_seen")) or "9")
        by_key[k] = merged

    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    kept = [r for r in by_key.values()
            if r.get("status") in ("saved", "applied") or _ts(r.get("last_seen")) >= cutoff]
    kept.sort(key=lambda r: (-(r.get("score") or 0), r.get("key")))
    return kept


def main(live_path: str, snap_path: str) -> None:
    try:
        live = json.load(open(live_path))
    except Exception as e:  # noqa: BLE001
        sys.exit(f"live pull unreadable: {e}")
    if not isinstance(live, list):
        sys.exit("live pull is not a list")
    try:
        old = json.load(open(snap_path))
    except FileNotFoundError:
        old = []
    out = merge(old, live)
    with open(snap_path, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"snapshot: {len(old)} before, {len(live)} live, {len(out)} after")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
