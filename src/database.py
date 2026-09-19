import sqlite3
from pathlib import Path
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "jobs.db"


VALID_STATUSES = {
    "New",
    "Interested",
    "Applied",
    "Interview",
    "Offer",
    "Rejected",
    "Not Interested",
    "Closed"
}


def get_connection():
    """
    Open a connection to the SQLite database.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    return connection


def initialize_database():
    """
    Create the jobs table if it does not exist.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            company TEXT,
            job_title TEXT,
            location TEXT,
            job_type TEXT,

            posting_date TEXT,
            date_found TEXT,

            sponsorship_status TEXT,

            match_score INTEGER,
            match_category TEXT,

            application_url TEXT UNIQUE,
            source TEXT,

            application_status TEXT
                DEFAULT 'New',

            why_it_matches TEXT,

            matched_resume_skills TEXT,
            matched_resume_experience TEXT,
            missing_skills TEXT,
            potential_gaps TEXT,
            suggested_resume_keywords TEXT,

            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    # Lightweight migration for databases created by earlier versions.
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(jobs)").fetchall()}
    for column in ("missing_skills", "potential_gaps", "suggested_resume_keywords"):
        if column not in existing:
            cursor.execute(f"ALTER TABLE jobs ADD COLUMN {column} TEXT")

    connection.commit()
    connection.close()


def serialize_list(items):
    """
    Convert a Python list into a simple text field.
    """

    if not items:
        return ""

    return " | ".join(
        str(item)
        for item in items
    )


def job_exists(application_url):
    """
    Check whether a job already exists.
    """

    if not application_url:
        return False

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM jobs
        WHERE application_url = ?
        """,
        (
            application_url,
        )
    )

    result = cursor.fetchone()

    connection.close()

    return result is not None


def insert_job(job):
    """
    Insert one new job.

    Existing application status is never erased.
    """

    application_url = job.get(
        "application_url"
    )

    if not application_url:
        return False

    if job_exists(application_url):
        return False

    now = datetime.now(
        timezone.utc
    ).isoformat()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO jobs (
            company,
            job_title,
            location,
            job_type,
            posting_date,
            date_found,
            sponsorship_status,
            match_score,
            match_category,
            application_url,
            source,
            application_status,
            why_it_matches,
            matched_resume_skills,
            matched_resume_experience,
            missing_skills,
            potential_gaps,
            suggested_resume_keywords,
            created_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            job.get("company"),
            job.get("title"),
            job.get("location"),
            job.get("job_type"),
            job.get("posting_date"),
            job.get("date_found"),
            job.get("sponsorship"),
            job.get("match_score"),
            job.get("match_category"),
            application_url,
            job.get("source"),
            "New",
            job.get("why_it_matches"),
            serialize_list(
                job.get(
                    "matched_resume_skills",
                    []
                )
            ),
            serialize_list(job.get("matched_resume_experience", [])),
            serialize_list(job.get("missing_skills", [])),
            serialize_list(job.get("potential_gaps", [])),
            serialize_list(job.get("suggested_resume_keywords", [])),
            now,
            now
        )
    )

    connection.commit()
    connection.close()

    return True


def update_existing_job(job):
    """
    Update job information without changing
    the user's application status.
    """

    application_url = job.get(
        "application_url"
    )

    if not application_url:
        return False

    if not job_exists(application_url):
        return False

    now = datetime.now(
        timezone.utc
    ).isoformat()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET
            company = ?,
            job_title = ?,
            location = ?,
            job_type = ?,
            posting_date = ?,
            sponsorship_status = ?,
            match_score = ?,
            match_category = ?,
            source = ?,
            why_it_matches = ?,
            matched_resume_skills = ?,
            matched_resume_experience = ?,
            missing_skills = ?,
            potential_gaps = ?,
            suggested_resume_keywords = ?,
            updated_at = ?
        WHERE application_url = ?
        """,
        (
            job.get("company"),
            job.get("title"),
            job.get("location"),
            job.get("job_type"),
            job.get("posting_date"),
            job.get("sponsorship"),
            job.get("match_score"),
            job.get("match_category"),
            job.get("source"),
            job.get("why_it_matches"),
            serialize_list(
                job.get(
                    "matched_resume_skills",
                    []
                )
            ),
            serialize_list(job.get("matched_resume_experience", [])),
            serialize_list(job.get("missing_skills", [])),
            serialize_list(job.get("potential_gaps", [])),
            serialize_list(job.get("suggested_resume_keywords", [])),
            now,
            application_url
        )
    )

    connection.commit()
    connection.close()

    return True


def save_jobs(jobs):
    """
    Save ranked jobs into the database.

    Returns:
        new_count
        updated_count
    """

    initialize_database()

    new_count = 0
    updated_count = 0

    for job in jobs:

        application_url = job.get(
            "application_url"
        )

        if not application_url:
            continue

        if job_exists(
            application_url
        ):
            update_existing_job(
                job
            )

            updated_count += 1

        else:
            inserted = insert_job(
                job
            )

            if inserted:
                new_count += 1

    return new_count, updated_count


def get_all_jobs():
    """
    Return all tracked jobs.
    """

    initialize_database()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM jobs
        ORDER BY
            match_score DESC,
            created_at DESC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def get_new_jobs():
    """
    Return jobs whose current status is New.
    """

    initialize_database()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM jobs
        WHERE application_status = 'New'
        ORDER BY
            match_score DESC,
            created_at DESC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def update_application_status(
    application_url,
    new_status
):
    """
    Update a job's application status.
    """

    if new_status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid application status: "
            f"{new_status}"
        )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET
            application_status = ?,
            updated_at = ?
        WHERE application_url = ?
        """,
        (
            new_status,
            now,
            application_url
        )
    )

    connection.commit()

    changed = (
        cursor.rowcount > 0
    )

    connection.close()

    return changed


def get_database_summary():
    """
    Return simple tracker statistics.
    """

    initialize_database()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        """
    )

    total_jobs = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        WHERE application_status = 'New'
        """
    )

    new_jobs = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        WHERE match_score >= 90
        """
    )

    excellent_matches = (
        cursor.fetchone()[0]
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        WHERE match_score >= 80
        AND match_score < 90
        """
    )

    strong_matches = (
        cursor.fetchone()[0]
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        WHERE COALESCE(sponsorship_status, '') NOT LIKE '%Does Not Sponsor%'
        """
    )

    sponsorship_compatible_jobs = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        WHERE application_status = 'Applied'
        """
    )

    applications_submitted = (
        cursor.fetchone()[0]
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        WHERE application_status = 'Interview'
        """
    )

    interviews = (
        cursor.fetchone()[0]
    )

    connection.close()

    return {
        "total_jobs": total_jobs,
        "new_jobs": new_jobs,
        "excellent_matches":
            excellent_matches,
        "strong_matches":
            strong_matches,
        "sponsorship_compatible_jobs":
            sponsorship_compatible_jobs,
        "applications_submitted":
            applications_submitted,
        "interviews":
            interviews
    }


def display_database_summary():
    """
    Print database statistics.
    """

    summary = get_database_summary()

    print()
    print(
        "=== Job Tracker Database ==="
    )
    print()

    print(
        f"Total Jobs: "
        f"{summary['total_jobs']}"
    )

    print(
        f"New Jobs: "
        f"{summary['new_jobs']}"
    )

    print(
        f"Excellent Matches: "
        f"{summary['excellent_matches']}"
    )

    print(
        f"Strong Matches: "
        f"{summary['strong_matches']}"
    )

    print(
        f"Sponsorship-Compatible Jobs: "
        f"{summary['sponsorship_compatible_jobs']}"
    )

    print(
        f"Applications Submitted: "
        f"{summary['applications_submitted']}"
    )

    print(
        f"Interviews: "
        f"{summary['interviews']}"
    )


if __name__ == "__main__":

    initialize_database()

    print(
        f"Database created at:"
    )

    print(
        DATABASE_PATH
    )

    display_database_summary()