"""The Muse adapter and the new payment-posting terms (HQ items p20261115jobs, p20261114jobs). No network."""
import source_muse as muse
from job_profile import SEARCH_TRACKS, TITLE_TOKENS
from scoring import score_job

SAMPLE = {"page": 1, "page_count": 1, "results": [
    {"id": 101, "name": "Payment Posting Specialist", "company": {"name": "Example Health"},
     "locations": [{"name": "Tampa, FL"}], "refs": {"landing_page": "https://example.com/j/101"},
     "publication_date": "2026-11-16T12:00:00Z",
     "contents": "<p>Post <b>payments</b> and work collections. Monday-Friday.</p>"},
    {"id": 102, "name": "", "company": {"name": "X"}, "locations": [], "refs": {"landing_page": "https://example.com/j/102"}},
    {"id": 103, "name": "No link", "company": {"name": "X"}, "locations": [], "refs": {}},
]}


def test_parse_keeps_good_postings_and_drops_broken_ones():
    jobs = muse.parse(SAMPLE, "tampa")
    assert [j.external_id for j in jobs] == ["101"]
    j = jobs[0]
    assert j.source == "themuse" and j.metro == "tampa" and j.location == "Tampa, FL"
    assert "Post payments" in j.description and "<" not in j.description


def test_parse_tolerates_an_empty_or_odd_response():
    assert muse.parse({}, "tampa") == [] and muse.parse(None, "jacksonville") == [] and muse.parse({"results": None}, "tampa") == []


def test_fetch_failure_returns_nothing_and_does_not_raise(monkeypatch):
    def boom(*a, **k): raise RuntimeError("down")
    monkeypatch.setattr(muse.httpx, "get", boom)
    assert muse.fetch("tampa") == []


def test_new_receivable_terms_are_searched_and_boosted():
    q = SEARCH_TRACKS["direct"]["queries"]
    for term in ("ar specialist", "payment posting specialist", "collections specialist", "cash applications analyst"):
        assert term in q
    assert "payment posting" in TITLE_TOKENS
    j = muse.parse(SAMPLE, "tampa")[0]
    score_job(j)
    assert j.score > 0
