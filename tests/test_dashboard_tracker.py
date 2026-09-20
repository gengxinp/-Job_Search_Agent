import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import database


def test_status_update_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        database,
        "DATABASE_PATH",
        tmp_path / "jobs.db",
    )

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

    assert database.update_application_status(
        job["application_url"],
        "Applied",
    )

    rows = database.get_all_jobs()

    assert rows[0]["application_status"] == "Applied"

    # A later search refresh must not erase
    # the user's application status.
    job["match_score"] = 91

    assert database.update_existing_job(job)

    rows = database.get_all_jobs()

    assert rows[0]["application_status"] == "Applied"
    assert rows[0]["match_score"] == 91


def test_summary_uses_master_prompt_score_bands(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        database,
        "DATABASE_PATH",
        tmp_path / "jobs.db",
    )

    database.initialize_database()

    jobs = [
        {
            "company": "Sponsor Co",
            "title": "Financial Analyst",
            "location": "New York, NY",
            "job_type": "Full-time",
            "posting_date": "2026-09-18",
            "date_found": "2026-09-18",
            "sponsorship": "Likely Sponsors",
            "match_score": 95,
            "match_category": "Excellent Match",
            "application_url": "https://example.com/1",
            "source": "Test",
        },
        {
            "company": "Unclear Co",
            "title": "Investment Analyst",
            "location": "New York, NY",
            "job_type": "Full-time",
            "posting_date": "2026-09-18",
            "date_found": "2026-09-18",
            "sponsorship": "Sponsorship Unclear",
            "match_score": 85,
            "match_category": "Strong Match",
            "application_url": "https://example.com/2",
            "source": "Test",
        },
        {
            "company": "Export Co",
            "title": "Finance Analyst",
            "location": "New York, NY",
            "job_type": "Full-time",
            "posting_date": "2026-09-18",
            "date_found": "2026-09-18",
            "sponsorship":
                "Work Authorization / Export Control Risk",
            "match_score": 75,
            "match_category": "Good Match",
            "application_url": "https://example.com/3",
            "source": "Test",
        },
    ]

    for job in jobs:
        assert database.insert_job(job)

    summary = database.get_database_summary()

    # Match-score bands
    assert summary["total_jobs"] == 3
    assert summary["new_jobs"] == 3
    assert summary["excellent_matches"] == 1
    assert summary["strong_matches"] == 1

    # Sponsorship categories
    assert summary["likely_sponsors"] == 1
    assert summary["sponsorship_unclear"] == 1
    assert summary["export_control_risk"] == 1

    # Tracker status
    assert summary["applications_submitted"] == 0
    assert summary["interviews"] == 0

    # The old misleading aggregate should not return.
    assert "sponsorship_compatible_jobs" not in summary