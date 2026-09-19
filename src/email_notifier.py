import os
import smtplib
import sqlite3
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yaml
from dotenv import load_dotenv


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "jobs.db"
CONFIG_PATH = BASE_DIR / "config" / "profile.yaml"
ENV_PATH = BASE_DIR / ".env"


# ============================================================
# CONFIG
# ============================================================

def load_profile():
    with open(
        CONFIG_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        return yaml.safe_load(file)


def load_environment():
    load_dotenv(
        ENV_PATH
    )


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def ensure_email_columns():
    """
    Add email tracking columns if they do not exist.
    """

    connection = get_connection()
    cursor = connection.cursor()

    columns = cursor.execute(
        "PRAGMA table_info(jobs)"
    ).fetchall()

    column_names = {
        row["name"]
        for row in columns
    }

    if "last_emailed_at" not in column_names:
        cursor.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN last_emailed_at TEXT
            """
        )

    connection.commit()
    connection.close()


# ============================================================
# SMART EMAIL RANKING
# ============================================================

def get_role_priority(job):
    """
    Give additional ranking priority to finance roles
    that are especially relevant to the target career path.

    This does NOT change the stored resume match score.
    It only affects weekly email ordering.
    """

    title = (
        job.get(
            "job_title",
            ""
        )
        or ""
    ).lower()

    # --------------------------------------------------------
    # Tier 1: Primary target roles
    # --------------------------------------------------------

    tier_1_keywords = [
        "financial analyst",
        "fp&a analyst",
        "fp&a",
        "strategic finance analyst",
        "corporate finance analyst",
        "investment analyst",
        "valuation analyst",
        "treasury analyst",
        "credit analyst",
    ]

    if any(
        keyword in title
        for keyword in tier_1_keywords
    ):
        return 30

    # --------------------------------------------------------
    # Tier 2: Highly relevant finance roles
    # --------------------------------------------------------

    tier_2_keywords = [
        "finance analyst",
        "research analyst",
        "portfolio analyst",
        "risk analyst",
        "investment banking analyst",
        "private equity analyst",
        "venture capital analyst",
        "capital markets analyst",
        "equity research analyst",
        "corporate development analyst",
    ]

    if any(
        keyword in title
        for keyword in tier_2_keywords
    ):
        return 20

    # --------------------------------------------------------
    # Tier 3: Adjacent analytical roles
    # --------------------------------------------------------

    tier_3_keywords = [
        "business analyst",
        "data analyst",
        "strategy analyst",
        "operations analyst",
        "commercial analyst",
        "pricing analyst",
        "revenue analyst",
    ]

    if any(
        keyword in title
        for keyword in tier_3_keywords
    ):
        return 10

    return 0


def get_seniority_penalty(job):
    """
    Lower the email priority of roles that appear
    substantially above entry / early-career level.

    This does NOT remove the job from the database.
    """

    title = (
        job.get(
            "job_title",
            ""
        )
        or ""
    ).lower()

    # Very senior roles
    very_senior_keywords = [
        "director",
        "vice president",
        "vp ",
        "head of",
        "chief ",
    ]

    if any(
        keyword in title
        for keyword in very_senior_keywords
    ):
        return -40

    # Manager / lead level
    manager_keywords = [
        "senior manager",
        "manager",
        "principal",
        "lead ",
    ]

    if any(
        keyword in title
        for keyword in manager_keywords
    ):
        return -25

    # Senior individual contributor
    if "senior" in title:
        return -15

    return 0


def calculate_email_ranking_score(job):
    """
    Email ranking score:

    Resume Match Score
    + Finance Role Priority
    + Seniority Adjustment

    Example:

    FP&A Analyst
    Resume score = 77
    Role priority = +30
    Email ranking = 107

    Business Analyst
    Resume score = 80
    Role priority = +10
    Email ranking = 90

    The FP&A role therefore appears first in the email.
    """

    base_score = int(
        job.get(
            "match_score",
            0
        )
        or 0
    )

    role_priority = get_role_priority(
        job
    )

    seniority_penalty = (
        get_seniority_penalty(
            job
        )
    )

    return (
        base_score
        + role_priority
        + seniority_penalty
    )


# ============================================================
# WEEKLY JOB SELECTION
# ============================================================

def get_weekly_jobs(
    minimum_score=70,
    days=7,
    limit=15
):
    """
    Return recent jobs that:

    1. Meet the minimum resume match score
    2. Were discovered recently
    3. Have not already been emailed
    4. Are ranked by career relevance
    5. Are limited to the Top 15 by default
    """

    ensure_email_columns()

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(days=days)
    ).date().isoformat()

    connection = get_connection()
    cursor = connection.cursor()

    rows = cursor.execute(
        """
        SELECT *
        FROM jobs
        WHERE
            match_score >= ?
            AND date_found >= ?
            AND COALESCE(sponsorship_status, '') != 'Likely Does Not Sponsor'
            AND application_url LIKE 'http%'
            AND (
                last_emailed_at IS NULL
                OR last_emailed_at = ''
            )
        """,
        (
            minimum_score,
            cutoff
        )
    ).fetchall()

    connection.close()

    jobs = [
        dict(row)
        for row in rows
    ]

    # --------------------------------------------------------
    # Smart ranking
    # --------------------------------------------------------

    jobs.sort(
        key=lambda job: (
            calculate_email_ranking_score(
                job
            ),
            int(
                job.get(
                    "match_score",
                    0
                )
                or 0
            )
        ),
        reverse=True
    )

    return jobs[:limit]


def mark_jobs_as_emailed(jobs):
    """
    Mark emailed jobs so they are not repeatedly sent.
    """

    if not jobs:
        return

    now = datetime.now(
        timezone.utc
    ).isoformat()

    connection = get_connection()
    cursor = connection.cursor()

    for job in jobs:

        application_url = job.get(
            "application_url"
        )

        if not application_url:
            continue

        cursor.execute(
            """
            UPDATE jobs
            SET last_emailed_at = ?
            WHERE application_url = ?
            """,
            (
                now,
                application_url
            )
        )

    connection.commit()
    connection.close()


# ============================================================
# MATCH CATEGORY
# ============================================================

def get_category(score):
    score = int(
        score or 0
    )

    if score >= 90:
        return "Excellent Match"

    if score >= 80:
        return "Strong Match"

    if score >= 70:
        return "Good Match"

    return "Lower Priority"


def summarize_weekly_jobs(jobs):
    return {
        "new_jobs": len(jobs),
        "excellent": sum(int(j.get("match_score", 0) or 0) >= 90 for j in jobs),
        "strong": sum(80 <= int(j.get("match_score", 0) or 0) < 90 for j in jobs),
        "potential_sponsorship": sum(
            j.get("sponsorship_status") in {"Likely Sponsors", "Sponsorship Unclear"}
            for j in jobs
        ),
    }


# ============================================================
# PLAIN TEXT EMAIL
# ============================================================

def build_plain_text_report(jobs):

    if not jobs:
        return (
            "Weekly AI Job Search Report\n\n"
            "No new matching jobs were found this week."
        )

    lines = []

    lines.append(
        "Weekly AI Job Search Report"
    )

    lines.append(
        "=" * 35
    )

    lines.append("")

    summary = summarize_weekly_jobs(jobs)
    lines.append(f"New Jobs Found: {summary['new_jobs']}")
    lines.append(f"Excellent Matches: {summary['excellent']}")
    lines.append(f"Strong Matches: {summary['strong']}")
    lines.append(f"Potential Sponsorship Matches: {summary['potential_sponsorship']}")
    lines.append("")

    for index, job in enumerate(
        jobs,
        start=1
    ):

        score = int(
            job.get(
                "match_score",
                0
            )
            or 0
        )

        company = job.get(
            "company",
            "Unknown"
        )

        title = job.get(
            "job_title",
            "Unknown"
        )

        location = job.get(
            "location",
            "Unknown"
        )

        sponsorship = job.get(
            "sponsorship_status",
            "Unknown"
        )

        why_it_matches = job.get(
            "why_it_matches"
        )

        application_url = job.get(
            "application_url",
            ""
        )

        lines.append(
            f"{index}. "
            f"{company} — {title}"
        )

        lines.append(
            f"Match Score: "
            f"{score}/100 "
            f"({get_category(score)})"
        )

        lines.append(
            f"Location: {location}"
        )

        lines.append(
            f"Sponsorship: {sponsorship}"
        )

        if why_it_matches:
            lines.append(
                f"Why it matches: "
                f"{why_it_matches}"
            )

        lines.append(
            f"Apply: {application_url}"
        )

        lines.append("")

        lines.append(
            "-" * 35
        )

        lines.append("")

    return "\n".join(
        lines
    )


# ============================================================
# HTML EMAIL
# ============================================================

def build_html_report(jobs):

    if not jobs:
        return """
        <html>
        <body>
            <h2>
                Weekly AI Job Search Report
            </h2>

            <p>
                No new matching jobs were found
                this week.
            </p>
        </body>
        </html>
        """

    cards = []

    for index, job in enumerate(
        jobs,
        start=1
    ):

        score = int(
            job.get(
                "match_score",
                0
            )
            or 0
        )

        company = job.get(
            "company",
            "Unknown"
        )

        title = job.get(
            "job_title",
            "Unknown"
        )

        location = job.get(
            "location",
            "Unknown"
        )

        sponsorship = job.get(
            "sponsorship_status",
            "Unknown"
        )

        why_match = job.get(
            "why_it_matches",
            ""
        )

        application_url = job.get(
            "application_url",
            ""
        )

        category = get_category(
            score
        )

        cards.append(
            f"""
            <div style="
                border:1px solid #ddd;
                border-radius:10px;
                padding:18px;
                margin-bottom:16px;
                font-family:Arial,sans-serif;
            ">

                <div style="
                    font-size:13px;
                    color:#666;
                    margin-bottom:8px;
                ">
                    Priority #{index}
                </div>

                <h3 style="
                    margin-top:0;
                    margin-bottom:12px;
                ">
                    {company} — {title}
                </h3>

                <p>
                    <strong>
                        Match Score:
                    </strong>

                    {score}/100
                    ({category})
                </p>

                <p>
                    <strong>
                        Location:
                    </strong>

                    {location}
                </p>

                <p>
                    <strong>
                        Sponsorship:
                    </strong>

                    {sponsorship}
                </p>

                <p>
                    <strong>
                        Why it matches:
                    </strong>

                    {why_match}
                </p>

                <p>
                    <a
                        href="{application_url}"
                        style="
                            display:inline-block;
                            padding:10px 16px;
                            background:#111827;
                            color:white;
                            text-decoration:none;
                            border-radius:6px;
                        "
                    >
                        Apply
                    </a>
                </p>

            </div>
            """
        )

    return f"""
    <html>

    <body style="
        font-family:Arial,sans-serif;
        max-width:800px;
        margin:auto;
        padding:20px;
    ">

        <h2>
            Weekly AI Job Search Report
        </h2>

        <p>Your top {len(jobs)} new opportunities, prioritized for finance career relevance.</p>
        <p>
            <strong>New Jobs Found:</strong> {summarize_weekly_jobs(jobs)['new_jobs']} &nbsp;|&nbsp;
            <strong>Excellent:</strong> {summarize_weekly_jobs(jobs)['excellent']} &nbsp;|&nbsp;
            <strong>Strong:</strong> {summarize_weekly_jobs(jobs)['strong']} &nbsp;|&nbsp;
            <strong>Potential Sponsorship:</strong> {summarize_weekly_jobs(jobs)['potential_sponsorship']}
        </p>

        {''.join(cards)}

    </body>

    </html>
    """


# ============================================================
# EMAIL SENDING
# ============================================================

def send_email(
    recipient,
    subject,
    plain_text,
    html_text
):

    load_environment()

    sender_email = os.getenv(
        "EMAIL_SENDER"
    )

    email_password = os.getenv(
        "EMAIL_APP_PASSWORD"
    )

    smtp_server = os.getenv(
        "SMTP_SERVER",
        "smtp.gmail.com"
    )

    smtp_port = int(
        os.getenv(
            "SMTP_PORT",
            "587"
        )
    )

    if not sender_email:
        raise ValueError(
            "EMAIL_SENDER is missing "
            "from .env"
        )

    if not email_password:
        raise ValueError(
            "EMAIL_APP_PASSWORD is missing "
            "from .env"
        )

    message = MIMEMultipart(
        "alternative"
    )

    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = recipient

    message.attach(
        MIMEText(
            plain_text,
            "plain",
            "utf-8"
        )
    )

    message.attach(
        MIMEText(
            html_text,
            "html",
            "utf-8"
        )
    )

    with smtplib.SMTP(
        smtp_server,
        smtp_port,
        timeout=30
    ) as server:

        server.starttls()

        server.login(
            sender_email,
            email_password
        )

        server.sendmail(
            sender_email,
            recipient,
            message.as_string()
        )


# ============================================================
# WEEKLY REPORT
# ============================================================

def send_weekly_report():

    profile = load_profile()

    notification_config = (
        profile.get(
            "notification",
            {}
        )
    )

    recipient = (
        notification_config.get(
            "email"
        )
    )

    if not recipient:
        raise ValueError(
            "Notification email is missing "
            "from config/profile.yaml"
        )

    if recipient == "YOUR_EMAIL@gmail.com":
        raise ValueError(
            "Replace YOUR_EMAIL@gmail.com "
            "in config/profile.yaml first."
        )

    minimum_score = (
        profile
        .get(
            "search",
            {}
        )
        .get(
            "minimum_match_score",
            70
        )
    )

    jobs = get_weekly_jobs(
        minimum_score=minimum_score,
        days=7,
        limit=15
    )

    subject = "Weekly AI Job Search Report"

    plain_text = (
        build_plain_text_report(
            jobs
        )
    )

    html_text = (
        build_html_report(
            jobs
        )
    )

    send_email(
        recipient=recipient,
        subject=subject,
        plain_text=plain_text,
        html_text=html_text
    )

    # Only mark jobs after the email
    # was successfully sent.
    mark_jobs_as_emailed(
        jobs
    )

    print()
    print(
        "Weekly email sent successfully."
    )

    print(
        f"Recipient: {recipient}"
    )

    print(
        f"Jobs included: {len(jobs)}"
    )


# ============================================================
# PREVIEW
# ============================================================

def preview_weekly_report():

    profile = load_profile()

    minimum_score = (
        profile
        .get(
            "search",
            {}
        )
        .get(
            "minimum_match_score",
            70
        )
    )

    jobs = get_weekly_jobs(
        minimum_score=minimum_score,
        days=7,
        limit=15
    )

    print()

    print(
        build_plain_text_report(
            jobs
        )
    )

    print()

    print(
        f"Jobs that would be emailed: "
        f"{len(jobs)}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print()

    print(
        "=== Weekly AI Job Search Email ==="
    )

    print()

    print(
        "Previewing email first..."
    )

    preview_weekly_report()

    print()

    print(
        "Email has NOT been sent."
    )

    print(
        "To send it, run:"
    )

    print(
        "python -c "
        "\"from src.email_notifier "
        "import send_weekly_report; "
        "send_weekly_report()\""
    )