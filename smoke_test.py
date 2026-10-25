"""
Offline smoke test -- no network, no API keys.

Runs the scoring engine and the store against mock postings modeled on real
listings, so you can sanity-check the ranking before wiring up any API.

    python smoke_test.py
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

    check_recency()
    check_purge()


def check_recency() -> None:
    """A fresh posting must outscore the same posting gone stale."""
    def aged(days: int) -> Job:
        stamp = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return Job(source="mock", external_id=f"age{days}", track="direct",
                   metro="san_antonio", title="Accounts Receivable Specialist",
                   company="Frost Bank", location="San Antonio, TX",
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


if __name__ == "__main__":
    main()
