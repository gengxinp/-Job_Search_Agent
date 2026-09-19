import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import database


def test_status_update_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "jobs.db")
    database.initialize_database()
    job = {
        "company": "Example Co",
        "title": "Financial Analyst",
        "location": "Los Angeles, CA",
        "job_type": "Full-time",
        "posting_date": "2026-09-18",
        "date_found": "2026-09-18",
        "sponsorship": "Sponsorship Unclear",
        "match_score": 88,
        "match_category": "Strong Match",
        "application_url": "https://example.com/job/1",
        "source": "Test",
    }
    assert database.insert_job(job)
    assert database.update_application_status(job["application_url"], "Applied")
    rows = database.get_all_jobs()
    assert rows[0]["application_status"] == "Applied"

    # A later search refresh must not erase the user's status.
    job["match_score"] = 91
    assert database.update_existing_job(job)
    rows = database.get_all_jobs()
    assert rows[0]["application_status"] == "Applied"
    assert rows[0]["match_score"] == 91


def test_summary_uses_master_prompt_score_bands(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "jobs.db")
    database.initialize_database()
    base = {
        "location": "New York, NY", "job_type": "Full-time",
        "posting_date": "2026-09-18", "date_found": "2026-09-18",
        "sponsorship": "Sponsorship Unclear", "source": "Test",
    }
    for i, score in enumerate((95, 85, 75), 1):
        j = dict(base, company=f"C{i}", title=f"Role{i}", match_score=score,
                 match_category="x", application_url=f"https://example.com/{i}")
        assert database.insert_job(j)
    summary = database.get_database_summary()
    assert summary["excellent_matches"] == 1
    assert summary["strong_matches"] == 1
    assert summary["sponsorship_compatible_jobs"] == 3
