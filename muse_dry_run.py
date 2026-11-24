"""Dry scan of The Muse: fetch Tampa Bay and Jacksonville postings and print what came back. Saves nothing.

    python muse_dry_run.py

Exits non-zero when a metro returns nothing, so the workflow goes red. HQ item p20261118jobs."""
import logging
import re
import sys

import source_muse as muse

FINANCE = re.compile(r"financ|account|analyst|treasury|audit|fp&a|controller|banking|credit|loan|underwrit|invest", re.I)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
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
