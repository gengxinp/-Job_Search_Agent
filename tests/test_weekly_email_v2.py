import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import email_notifier


def test_email_category_has_no_possible_band():
    assert email_notifier.get_category(69) == "Lower Priority"
    assert email_notifier.get_category(70) == "Good Match"


def test_weekly_query_hard_excludes_no_sponsor(tmp_path, monkeypatch):
    db = tmp_path / "jobs.db"
    monkeypatch.setattr(email_notifier, "DATABASE_PATH", db)
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE jobs (
        application_url TEXT, match_score INTEGER, date_found TEXT,
        sponsorship_status TEXT, last_emailed_at TEXT, job_title TEXT,
        company TEXT, location TEXT, why_it_matches TEXT
    )""")
    today = datetime.now(timezone.utc).date().isoformat()
    con.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)", [
        ("https://example.com/no", 99, today, "Likely Does Not Sponsor", None, "Financial Analyst", "A", "US", "fit"),
        ("https://example.com/unclear", 80, today, "Sponsorship Unclear", None, "Financial Analyst", "B", "US", "fit"),
        ("https://example.com/yes", 85, today, "Likely Sponsors", None, "Financial Analyst", "C", "US", "fit"),
    ])
    con.commit(); con.close()
    jobs = email_notifier.get_weekly_jobs(minimum_score=70, days=7, limit=15)
    assert {j["company"] for j in jobs} == {"B", "C"}


def test_weekly_subject_exact(monkeypatch):
    monkeypatch.setattr(email_notifier, "load_profile", lambda: {"notification": {"email": "x@example.com"}, "search": {"minimum_match_score": 70}})
    monkeypatch.setattr(email_notifier, "get_weekly_jobs", lambda **kwargs: [])
    captured = {}
    monkeypatch.setattr(email_notifier, "send_email", lambda **kwargs: captured.update(kwargs))
    monkeypatch.setattr(email_notifier, "mark_jobs_as_emailed", lambda jobs: None)
    email_notifier.send_weekly_report()
    assert captured["subject"] == "Weekly AI Job Search Report"
