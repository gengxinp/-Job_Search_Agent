import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from job_matcher import score_job

PROFILE={"candidate":{"requires_future_sponsorship":True}}
RESUME={"skills":["Excel","Financial Modeling","Valuation"],"education":["Master's degree"],"experience_keywords":["Financial Analysis","Valuation"]}

def test_resume_details_are_created_without_ai():
    job={"title":"Financial Analyst","description":"Requires Excel, SQL, financial modeling and valuation. 2+ years preferred.","location":"Los Angeles, CA","sponsorship":"Sponsorship Unclear"}
    result=score_job(job,PROFILE,RESUME)
    assert "Excel" in result["matched_resume_skills"]
    assert "SQL" in result["missing_skills"]
    assert "Excel" in result["suggested_resume_keywords"]
    assert any("2 years" in x for x in result["potential_gaps"])

def test_suggested_keywords_never_add_missing_skill():
    job={"title":"Financial Analyst","description":"SQL and Python required.","location":"New York, NY","sponsorship":"Sponsorship Unclear"}
    result=score_job(job,PROFILE,RESUME)
    assert "SQL" in result["missing_skills"] and "Python" in result["missing_skills"]
    assert "SQL" not in result["suggested_resume_keywords"]
    assert "Python" not in result["suggested_resume_keywords"]
