"""
Offline smoke test -- no network, no API keys.

Runs the scoring engine and the store against mock postings modeled on real
listings, so you can sanity-check the ranking before wiring up any API.

    python smoke_test.py
"""

import os

os.environ.setdefault("DB_PATH", "/tmp/jobscan_smoke.db")

from app.scoring import Job, rank          # noqa: E402
from app import store                      # noqa: E402

MOCK = [
    Job(source="mock", external_id="1", track="direct", metro="san_antonio",
        title="Accounts Receivable Specialist",
        company="Frost Bank",
        location="San Antonio, TX",
        url="https://example.com/1",
        salary_min=52000, salary_max=64000,
        description=("Responsible for cash application, posting payments, account "
                     "reconciliation, aging report review and resolving invoice "
                     "disputes with high volume customer service. Excel required.")),

    Job(source="mock", external_id="2", track="stretch", metro="san_antonio",
        title="BSA/AML Analyst I",
        company="Credit Human Federal Credit Union",
        location="San Antonio, TX",
        url="https://example.com/2",
        salary_min=58000, salary_max=72000,
        description=("Perform AML alert reviews, KYC verification, and document "
                     "suspicious activity. Banking or branch experience preferred. "
                     "Compliance and risk exposure a plus.")),

    Job(source="mock", external_id="3", track="direct", metro="dallas",
        title="Will Call Coordinator",
        company="Sysco Dallas",
        location="Dallas, TX",
        url="https://example.com/3",
        salary_min=46000, salary_max=51000,
        description=("Manage will call counter, receiving paperwork, order selection "
                     "and warehouse coordination for distribution customers.")),

    Job(source="mock", external_id="4", track="stretch", metro="dallas",
        title="Director of Accounts Receivable",
        company="Regional Health System",
        location="Dallas, TX",
        url="https://example.com/4",
        salary_min=120000, salary_max=150000,
        description=("Lead the AR function. CPA required. 10+ years of progressive "
                     "accounting leadership experience.")),

    Job(source="mock", external_id="5", track="growth", metro="san_antonio",
        title="Patient Financial Services Representative",
        company="Methodist Healthcare",
        location="San Antonio, TX",
        url="https://example.com/5",
        salary_min=38000, salary_max=44000,
        description=("Billing, collections and insurance follow-up for hospital "
                     "accounts. Customer service focus.")),

    Job(source="mock", external_id="6", track="growth", metro="san_antonio",
        title="Warehouse Associate",
        company="Local Distributor",
        location="San Antonio, TX",
        url="https://example.com/6",
        salary_min=34000, salary_max=38000,
        description="Pick and pack orders. Must have own vehicle. Commission only bonus."),
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


if __name__ == "__main__":
    main()
