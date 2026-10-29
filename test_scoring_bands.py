"""Pins known-good and known-bad postings to their score bands.

    python test_scoring_bands.py
"""
from scoring import Job, score_job


def job(title, desc, track="stretch", lo=60000, hi=70000):
    return score_job(Job(source="t", external_id=title, title=title, company="Test Co", location="Tampa, FL",
                         url="https://example.com", description=desc, salary_min=lo, salary_max=hi,
                         metro="tampa", track=track))


# (posting, minimum score). Analyst roles that match the resume must clear 70; the
# core direct-track roles land lower on the scale because direct carries no track boost.
GOOD = [
    (job("Associate Analyst - Bank Fraud Detection Operations",
        "Review fraud alerts, KYC checks and suspicious activity on consumer banking accounts."), 70),
    (job("Cash Application Specialist", "Post payments, cash application, reconciliation and aging report review.",
        track="direct", lo=55000, hi=64000), 60),
]
BAD = [
    job("Network Operations Analyst", "Monitor routers, firewalls and network uptime."),
    job("Operations Analyst (Drafting Support - Advanced (9-15 yrs))", "AutoCAD drafting for engineering drawings."),
]


def main():
    ok = True
    for j, floor in GOOD:
        print(f"{j.score:5.1f}  good  {j.title} (needs {floor}+)")
        ok &= j.score >= floor
    for j in BAD:
        print(f"{j.score:5.1f}  bad   {j.title}")
        ok &= j.score < 50
    if not ok:
        raise SystemExit("score bands off: good roles must clear their floor, unrelated roles under 50")
    print("score bands OK")


if __name__ == "__main__":
    main()
