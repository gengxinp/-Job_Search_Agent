import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from job_filter import clearly_too_senior, title_matches_target_role

PROFILE = {"search": {"hard_reject_years_experience": 4}}
ROLES = ["Financial Analyst", "Corporate Development Analyst", "Investment Analyst"]

def job(title, description=""):
    return {"title": title, "description": description}

def test_professional_analyst_without_campus_label_is_kept():
    assert not clearly_too_senior(job("Financial Analyst", "2+ years of relevant experience preferred"), PROFILE)
    assert title_matches_target_role("Financial Analyst", ROLES)

def test_professional_associate_with_three_years_is_kept():
    assert not clearly_too_senior(job("Corporate Development Associate", "3+ years of relevant experience"), PROFILE)

def test_four_plus_year_requirement_is_rejected():
    assert clearly_too_senior(job("Investment Analyst", "4+ years of professional experience required"), PROFILE)

def test_senior_title_is_rejected_even_without_years():
    assert clearly_too_senior(job("Senior Financial Analyst"), PROFILE)
