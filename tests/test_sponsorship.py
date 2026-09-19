import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_filter import classify_sponsorship, filter_job

PROFILE = {
    "candidate": {"requires_future_sponsorship": True},
    "target_roles": ["Financial Analyst"],
    "job_preferences": {"job_types": ["full_time"]},
    "locations": ["United States"],
}


def job(description):
    return {"title": "Financial Analyst", "description": description,
            "job_type": "Full-time", "location": "Los Angeles, CA"}


def test_explicit_no_sponsor():
    assert classify_sponsorship(job("We do not provide sponsorship now or in the future.")) == "Likely Does Not Sponsor"


def test_unrestricted_authorization_is_no_sponsor():
    assert classify_sponsorship(job("Candidates must have unrestricted work authorization in the U.S.")) == "Likely Does Not Sponsor"


def test_unclear_is_preserved():
    assert classify_sponsorship(job("Bachelor's degree required.")) == "Sponsorship Unclear"


def test_no_sponsor_is_hard_reject():
    j = job("We cannot sponsor employment visas.")
    j["sponsorship"] = classify_sponsorship(j)
    keep, reason = filter_job(j, PROFILE)
    assert keep is False
    assert "sponsor" in reason.lower()


def test_application_page_can_turn_unclear_into_no_sponsor(monkeypatch):
    import job_filter
    class Response:
        text = "<html>Applicants must be authorized to work without current or future sponsorship.</html>"
        def raise_for_status(self): pass
    monkeypatch.setattr(job_filter.requests, "get", lambda *a, **k: Response())
    j = job("Bachelor's degree required.")
    j["application_url"] = "https://example.com/job"
    j["sponsorship"] = "Sponsorship Unclear"
    assert job_filter.verify_sponsorship_on_application_page(j) == "Likely Does Not Sponsor"

def test_basic_work_authorization_alone_is_not_automatic_no_sponsor():
    j = job(
        "Candidates must be authorized to work in the United States."
    )
    assert classify_sponsorship(j) == "Sponsorship Unclear"


def test_itar_us_person_only_is_no_sponsor():
    j = job(
        "To conform to U.S. Government export regulations, "
        "applicant must be a U.S. citizen or national, "
        "U.S. lawful permanent resident (green card holder), "
        "refugee, or asylee."
    )
    assert classify_sponsorship(j) == "Likely Does Not Sponsor"


def test_itar_with_possible_government_authorization_is_not_auto_rejected():
    j = job(
        "To conform to U.S. Government export regulations, "
        "applicant must be a U.S. citizen or national, "
        "U.S. lawful permanent resident (green card holder), "
        "refugee, or asylee, or be eligible to obtain the "
        "required authorizations from the U.S. Department of State."
    )
    assert classify_sponsorship(j) == "Work Authorization / Export Control Risk"