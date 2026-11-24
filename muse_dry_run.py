"""Dry scan of The Muse: fetch Tampa Bay and Jacksonville postings and print what came back. Saves nothing.

    python muse_dry_run.py

Exits non-zero when a metro returns nothing, so the workflow goes red. HQ item p20261118jobs."""
import logging
import re
import sys

import source_muse as muse

FINANCE = re.compile(r"financ|account|analyst|treasury|audit|fp&a|controller|banking|credit|loan|underwrit|invest", re.I)


def probe() -> None:
    """Print the HTTP status of a few request shapes, to see which one the feed accepts."""
    import httpx
    for params in ({"page": 1}, {"page": 0}, {"page": 1, "category": "Accounting and Finance"},
                   {"page": 1, "location": "Tampa, FL"}, {"page": 0, "location": "Tampa, FL"},
                   {"page": 0, "location": "Florida"}):
        try:
            r = httpx.get(muse.BASE, params=params, headers=muse.HEADERS, timeout=25)
            body = r.text[:120].replace("\n", " ")
            print(f"probe {params} -> {r.status_code} {body}")
        except Exception as e:  # noqa: BLE001
            print(f"probe {params} -> {type(e).__name__}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    probe()
    bad = 0
    for metro in ("tampa", "jacksonville"):
        jobs = muse.fetch(metro)
        fin = [j for j in jobs if FINANCE.search(j.title)]
        print(f"{metro}: {len(jobs)} postings, {len(fin)} with finance-style titles")
        for j in (fin or jobs)[:3]:
            print(f"   - {j.title} | {j.company} | {j.location}")
        if not jobs:
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
