"""
Smoke test.

    python smoke_test.py                 offline: no network, no API keys
    python smoke_test.py --live URL      also runs one real scan against a
                                         deployed instance (needs CRON_TOKEN
                                         in the environment if one is set)

Offline, it runs the scoring engine, the store and a full scan pipeline
against mock postings modeled on real listings. Either way it exits non-zero
-- and says why -- if a scan saves zero jobs.
"""

import os

os.environ.setdefault("DB_PATH", "/tmp/jobscan_smoke.db")

from datetime import datetime, timedelta, timezone   # noqa: E402

from scoring import Job, rank, score_job             # noqa: E402
import store                                         # noqa: E402

MOCK = [
    Job(source="mock", external_id="1", track="direct", metro="tampa",
        title="Accounts Receivable Specialist",
        company="Raymond James",
        location="Tampa, FL",
        url="https://example.com/1",
        salary_min=52000, salary_max=64000,
        description=("Responsible for cash application, posting payments, account "
                     "reconciliation, aging report review and resolving invoice "
                     "disputes with high volume customer service. Excel required.")),

    Job(source="mock", external_id="2", track="stretch", metro="tampa",
        title="BSA/AML Analyst I",
        company="Suncoast Credit Union",
        location="Tampa, FL",
        url="https://example.com/2",
        salary_min=58000, salary_max=72000,
        description=("Perform AML alert reviews, KYC verification, and document "
                     "suspicious activity. Banking or branch experience preferred. "
                     "Compliance and risk exposure a plus.")),

    Job(source="mock", external_id="3", track="direct", metro="jacksonville",
        title="Will Call Coordinator",
        company="Sysco Jacksonville",
        location="Jacksonville, FL",
        url="https://example.com/3",
        salary_min=46000, salary_max=51000,
        description=("Manage will call counter, receiving paperwork, order selection "
                     "and warehouse coordination for distribution customers.")),

    Job(source="mock", external_id="4", track="stretch", metro="jacksonville",
        title="Director of Accounts Receivable",
        company="Regional Health System",
        location="Jacksonville, FL",
        url="https://example.com/4",
        salary_min=120000, salary_max=150000,
        description=("Lead the AR function. CPA required. 10+ years of progressive "
                     "accounting leadership experience.")),

    Job(source="mock", external_id="5", track="growth", metro="tampa",
        title="Patient Financial Services Representative",
        company="BayCare Health System",
        location="Tampa, FL",
        url="https://example.com/5",
        salary_min=38000, salary_max=44000,
        description=("Billing, collections and insurance follow-up for hospital "
                     "accounts. Customer service focus.")),

    Job(source="mock", external_id="6", track="growth", metro="tampa",
        title="Warehouse Associate",
        company="Local Distributor",
        location="Tampa, FL",
        url="https://example.com/6",
        salary_min=34000, salary_max=38000,
        description="Pick and pack orders. Must have own vehicle. Commission only bonus."),

    Job(source="mock", external_id="7", track="direct", metro="orlando",
        title="Cash Application Specialist",
        company="Orlando Health",
        location="Orlando, FL",
        url="https://example.com/7",
        salary_min=50000, salary_max=58000,
        description=("Apply incoming payments, research unapplied cash, "
                     "reconciliation and aging report review. Excel required.")),

    Job(source="mock", external_id="9", track="operations", metro="orlando",
        title="Warehouse Supervisor",
        company="Publix Distribution",
        location="Orlando, FL",
        url="https://example.com/9",
        salary_min=52000, salary_max=61000,
        description=("Lead the receiving and shipping crew, cycle count and "
                     "inventory accuracy, forklift certified. Monday-Friday "
                     "day shift.")),

    Job(source="mock", external_id="10", track="trades", metro="jacksonville",
        title="HVAC Apprentice",
        company="Comfort Air Services",
        location="Jacksonville, FL",
        url="https://example.com/10",
        salary_min=40000, salary_max=52000,
        description=("Paid training and apprenticeship, certification provided. "
                     "No experience required. Weekends off.")),

    Job(source="mock", external_id="11", track="operations", metro="tampa",
        title="Shipping and Receiving Clerk",
        company="Regional Freight",
        location="Tampa, FL",
        url="https://example.com/11",
        salary_min=36000, salary_max=40000,
        description=("Shipping, receiving, loading dock. Mandatory weekends, "
                     "6 days a week during peak.")),

    Job(source="mock", external_id="8", track="direct", metro="tallahassee",
        title="Relationship Banker",
        company="Capital City Bank",
        location="Tallahassee, FL",
        url="https://example.com/8",
        salary_min=42000, salary_max=50000,
        description=("Account opening, consumer banking, client relationship "
                     "management and fraud awareness in a branch setting.")),
]


def main() -> None:
    ranked = rank(MOCK, minimum=0)  # minimum=0 so we can see everything, including rejects

    print(f"{'SCORE':>6}  {'TRACK':<8} {'METRO':<12} TITLE")
    print("-" * 78)
    for j in ranked:
        print(f"{j.score:>6.1f}  {j.track:<8} {j.metro:<12} {j.title} — {j.company}")
        for r in j.reasons:
            print(f"         + {r}")
        for f in j.flags:
            print(f"         ! {f}")
        print()

    store.init_db()
    new = store.upsert_jobs(ranked)
    again = store.upsert_jobs(ranked)   # must be 0 -- dedupe check
    print(f"stored: {new} new on first pass, {again} new on second pass (dedupe works if 0)")
    print("top of board:", [j["title"] for j in store.get_jobs(limit=3)])

    check_schedule()
    check_budget()
    check_scan_saves_jobs()
    check_recency()
    check_purge()


def check_recency() -> None:
    """A fresh posting must outscore the same posting gone stale."""
    def aged(days: int) -> Job:
        stamp = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return Job(source="mock", external_id=f"age{days}", track="direct",
                   metro="tampa", title="Accounts Receivable Specialist",
                   company="Raymond James", location="Tampa, FL",
                   url="https://example.com/age", salary_min=52000, salary_max=64000,
                   posted_at=stamp,
                   description="Cash application, posting payments, reconciliation.")

    fresh, week, stale = (score_job(aged(d)).score for d in (1, 5, 40))

    undated = aged(1)
    undated.posted_at = "not a real date"
    unparseable = score_job(undated).score

    print("\nrecency:")
    print(f"   1 day old  {fresh:5.1f}")
    print(f"   5 days old {week:5.1f}")
    print(f"  40 days old {stale:5.1f}")
    assert fresh > week > stale, "fresher postings must score higher"
    assert unparseable == score_job(aged(60)).score + 8.0, "bad dates must be neutral"
    print("  unparseable date is neutral, not penalized — ok")


def check_purge() -> None:
    """Stale rows go; anything the user acted on stays."""
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(timespec="seconds")
    with store.conn() as c:
        keys = [r["key"] for r in c.execute("SELECT key FROM jobs LIMIT 3").fetchall()]
        for k in keys:
            c.execute("UPDATE jobs SET last_seen = ? WHERE key = ?", (old, k))
        c.execute("UPDATE jobs SET status = 'applied' WHERE key = ?", (keys[0],))

    purged = store.purge_stale(14)
    survived = [j["status"] for j in store.get_jobs(limit=50)]
    print(f"\npurge: removed {purged} stale rows, kept {survived.count('applied')} applied")
    assert "applied" in survived, "applied jobs must never be purged"



def check_schedule() -> None:
    """Weekends off must beat a six-day week, all else equal."""
    def posting(desc: str) -> Job:
        return Job(source="mock", external_id="sched", track="operations",
                   metro="tampa", title="Warehouse Lead", company="Co",
                   location="Tampa, FL", url="https://example.com/s",
                   salary_min=50000, salary_max=55000, description=desc)

    off = score_job(posting("Inventory and shipping. Monday-Friday, weekends off.")).score
    plain = score_job(posting("Inventory and shipping.")).score
    six = score_job(posting("Inventory and shipping. 6 days a week.")).score
    print(f"\nschedule: weekends off {off:.1f} > unstated {plain:.1f} > six days {six:.1f}")
    assert off > plain > six, "schedule language must move the score"


def check_budget() -> None:
    """A scan spends exactly the budget, and the window mixes tracks and metros."""
    import scanner
    from job_profile import METROS, SEARCH_TRACKS

    total = len(scanner._all_searches())
    today = scanner.todays_searches()
    tracks = {t for t, _, _ in today}
    metros = {m for _, _, m in today}
    days = -(-total // scanner.CALLS_PER_RUN)
    print(f"budget: {len(today)} calls/scan of {total} combos, full cycle every {days} days")
    print(f"        today covers {len(tracks)}/{len(SEARCH_TRACKS)} tracks, "
          f"{len(metros)}/{len(METROS)} metros")
    assert len(today) == scanner.CALLS_PER_RUN, "scan must spend exactly the budget"
    assert len(metros) == len(METROS), "every window should touch every metro"


def check_scan_saves_jobs() -> None:
    """The full scan path -- fetch, score, dedupe, store -- must save something.

    Sources are stubbed to return realistic Florida postings for whatever
    (track, query, metro) today's rotation picks, so this exercises the real
    run_scan() wiring: METROS, the call budget, MIN_SCORE, and the store.
    If a config change makes every posting fall under the threshold, or
    points the scan at metros the sources don't serve, this fails.
    """
    import scanner
    import store as store_mod
    from job_profile import METROS

    calls: list[tuple[str, str, str]] = []

    def fake_fetch(track: str, query: str, metro_key: str) -> list[Job]:
        calls.append((track, query, metro_key))
        city = METROS[metro_key]["label"]
        return [Job(source="stub", external_id=f"{metro_key}-{track}-{len(calls)}",
                    track=track, metro=metro_key,
                    title="Accounts Receivable Specialist" if track != "trades" else "HVAC Apprentice",
                    company=f"Stub Employer {len(calls)}", location=city,
                    url="https://example.com/stub", salary_min=50000, salary_max=60000,
                    description=("Cash application, reconciliation, invoice review, "
                                 "paid training and apprenticeship. Monday-Friday."))]

    saved_db = store_mod.DB_PATH
    store_mod.DB_PATH = "/tmp/jobscan_smoke_scan.db"
    if os.path.exists(store_mod.DB_PATH):
        os.remove(store_mod.DB_PATH)
    patched = {
        "adzuna_available": scanner.adzuna.available, "adzuna_fetch": scanner.adzuna.fetch,
        "jsearch_available": scanner.jsearch.available, "boards": dict(scanner.COMPANY_BOARDS),
    }
    scanner.adzuna.available = lambda: True
    scanner.adzuna.fetch = fake_fetch
    scanner.jsearch.available = lambda: False
    scanner.COMPANY_BOARDS.clear()
    try:
        result = scanner.run_scan()
        stored = store_mod.stats()["total"]
    finally:
        scanner.adzuna.available = patched["adzuna_available"]
        scanner.adzuna.fetch = patched["adzuna_fetch"]
        scanner.jsearch.available = patched["jsearch_available"]
        scanner.COMPANY_BOARDS.update(patched["boards"])
        store_mod.DB_PATH = saved_db

    metros_hit = sorted({m for _, _, m in calls})
    print(f"\nscan pipeline: {len(calls)} searches across {metros_hit}")
    print(f"               found {result['found']}, kept {result['kept']}, saved {stored}")
    assert_scan_saved(result["found"], result["kept"], stored, where="offline scan")


def assert_scan_saved(found: int, kept: int, stored: int, where: str) -> None:
    """Fail loudly on a zero-save scan, naming the most likely cause."""
    if stored > 0 and kept > 0:
        return
    if found == 0:
        why = ("the sources returned nothing -- check /health for missing "
               "credentials, and that METROS names places the sources cover")
    elif kept == 0:
        why = (f"all {found} postings scored under MIN_SCORE -- the scoring "
               "profile no longer matches what the searches return")
    else:
        why = f"{kept} postings were kept but none reached the database"
    raise SystemExit(f"FAIL ({where}): scan saved 0 jobs -- {why}")


def check_live(base_url: str) -> None:
    """Run one real scan on a deployed instance and fail if it saves nothing."""
    import json
    import urllib.request

    token = os.getenv("CRON_TOKEN", "")
    url = f"{base_url.rstrip('/')}/api/scan?wait=true" + (f"&token={token}" if token else "")
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.load(resp)
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=60) as resp:
        stored = json.load(resp)["total"]

    print(f"\nlive scan: found {result['found']}, kept {result['kept']}, "
          f"new {result['new']}, board now holds {stored} (sources: {result.get('sources')})")
    assert_scan_saved(result["found"], result["kept"], stored, where="live scan")


if __name__ == "__main__":
    import sys

    main()
    if "--live" in sys.argv:
        check_live(sys.argv[sys.argv.index("--live") + 1])
    print("\nall checks passed")
