import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "jobs.db"

st.set_page_config(
    page_title="AI Job Search Agent",
    page_icon="💼",
    layout="wide",
)


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection():
    return sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False
    )


def get_table_columns():
    conn = get_connection()

    try:
        rows = conn.execute(
            "PRAGMA table_info(jobs)"
        ).fetchall()

        return [
            row[1]
            for row in rows
        ]

    finally:
        conn.close()


def load_jobs():
    conn = get_connection()

    try:
        df = pd.read_sql_query(
            """
            SELECT *
            FROM jobs
            ORDER BY match_score DESC
            """,
            conn
        )

        return df

    finally:
        conn.close()


def update_application_status(
    job_id,
    new_status
):
    conn = get_connection()

    try:
        conn.execute(
            """
            UPDATE jobs
            SET application_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                new_status,
                datetime.now(timezone.utc).isoformat(),
                job_id
            )
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_column(
    df,
    column_name,
    default=""
):
    if column_name in df.columns:
        return df[column_name]

    return pd.Series(
        [default] * len(df),
        index=df.index
    )


def get_match_category(score):
    try:
        score = float(score)
    except Exception:
        return "Unknown"

    if score >= 90:
        return "Excellent Match"

    if score >= 80:
        return "Strong Match"

    if score >= 70:
        return "Good Match"

    return "Lower Priority"


def normalize_status(value):
    if value is None:
        return "New"

    value = str(value).strip()

    if not value:
        return "New"

    return value


# ============================================================
# PAGE HEADER
# ============================================================

st.title("💼 AI Job Search Agent")

st.caption(
    "Resume-based job discovery, ranking, "
    "sponsorship screening, and application tracking."
)

st.divider()


# ============================================================
# CHECK DATABASE
# ============================================================

if not DATABASE_PATH.exists():

    st.error(
        "Job database was not found."
    )

    st.code(
        "python src/main.py"
    )

    st.stop()


table_columns = get_table_columns()

if not table_columns:

    st.error(
        "The jobs table does not exist yet."
    )

    st.code(
        "python src/main.py"
    )

    st.stop()


jobs = load_jobs()


# ============================================================
# EMPTY DATABASE
# ============================================================

if jobs.empty:

    st.warning(
        "No jobs are currently stored "
        "in the database."
    )

    st.code(
        "python src/main.py"
    )

    st.stop()


# ============================================================
# PREPARE DATA
# ============================================================

if "application_status" not in jobs.columns:
    jobs["application_status"] = "New"

jobs["application_status"] = (
    jobs["application_status"]
    .apply(normalize_status)
)

if "match_score" not in jobs.columns:
    jobs["match_score"] = 0

jobs["match_score"] = pd.to_numeric(
    jobs["match_score"],
    errors="coerce"
).fillna(0)

jobs["match_category"] = (
    jobs["match_score"]
    .apply(get_match_category)
)


# ============================================================
# SUMMARY METRICS
# ============================================================

total_jobs = len(jobs)

# "New jobs this week" is based on discovery date,
# not application status.
if "date_found" in jobs.columns:
    found_dates = pd.to_datetime(
        jobs["date_found"],
        errors="coerce",
        utc=True
    )

    week_cutoff = (
        pd.Timestamp.now(tz="UTC")
        - pd.Timedelta(days=7)
    )

    new_jobs = int(
        (found_dates >= week_cutoff).sum()
    )

else:
    new_jobs = 0


excellent_matches = (
    jobs["match_score"] >= 90
).sum()


strong_matches = (
    (jobs["match_score"] >= 80)
    &
    (jobs["match_score"] < 90)
).sum()


applications = (
    jobs["application_status"]
    .eq("Applied")
    .sum()
)


interviews = (
    jobs["application_status"]
    .eq("Interview")
    .sum()
)


# ------------------------------------------------------------
# SPONSORSHIP METRICS
# ------------------------------------------------------------

if "sponsorship_status" in jobs.columns:

    sponsorship_series = (
        jobs["sponsorship_status"]
        .fillna("")
        .astype(str)
    )

    sponsorship_likely = (
        sponsorship_series
        .eq("Likely Sponsors")
        .sum()
    )

    sponsorship_unclear = (
        sponsorship_series
        .eq("Sponsorship Unclear")
        .sum()
    )

    export_control_risk = (
        sponsorship_series
        .eq(
            "Work Authorization / Export Control Risk"
        )
        .sum()
    )

else:

    sponsorship_likely = 0
    sponsorship_unclear = 0
    export_control_risk = 0


# ------------------------------------------------------------
# DISPLAY SUMMARY METRICS
# ------------------------------------------------------------

metric_columns = st.columns(9)

metric_columns[0].metric(
    "Total Jobs",
    total_jobs
)

metric_columns[1].metric(
    "New This Week",
    new_jobs
)

metric_columns[2].metric(
    "Excellent",
    excellent_matches
)

metric_columns[3].metric(
    "Strong",
    strong_matches
)

metric_columns[4].metric(
    "Likely Sponsors",
    sponsorship_likely
)

metric_columns[5].metric(
    "Sponsorship Unclear",
    sponsorship_unclear
)

metric_columns[6].metric(
    "Export Control Risk",
    export_control_risk
)

metric_columns[7].metric(
    "Applied",
    applications
)

metric_columns[8].metric(
    "Interviews",
    interviews
)

st.divider()


# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.header(
    "Job Filters"
)


# ------------------------------------------------------------
# SEARCH
# ------------------------------------------------------------

search_text = st.sidebar.text_input(
    "Search Job Title / Company",
    placeholder="Financial Analyst"
)


# ------------------------------------------------------------
# LOCATION
# ------------------------------------------------------------

if "location" in jobs.columns:

    locations = sorted(
        jobs["location"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

else:
    locations = []


selected_locations = (
    st.sidebar.multiselect(
        "Location",
        locations
    )
)


# ------------------------------------------------------------
# JOB TYPE
# ------------------------------------------------------------

if "job_type" in jobs.columns:

    job_types = sorted(
        jobs["job_type"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

else:
    job_types = []


selected_job_types = (
    st.sidebar.multiselect(
        "Job Type",
        job_types
    )
)


# ------------------------------------------------------------
# STATUS
# ------------------------------------------------------------

statuses = [
    "New",
    "Interested",
    "Applied",
    "Interview",
    "Offer",
    "Rejected",
    "Not Interested",
    "Closed"
]


selected_statuses = (
    st.sidebar.multiselect(
        "Application Status",
        statuses
    )
)


# ------------------------------------------------------------
# MATCH SCORE
# ------------------------------------------------------------

minimum_score = st.sidebar.slider(
    "Minimum Match Score",
    min_value=0,
    max_value=100,
    value=0,
    step=5
)


# ------------------------------------------------------------
# SPONSORSHIP
# ------------------------------------------------------------

sponsorship_column = None

for possible_column in [
    "sponsorship_status",
    "sponsorship",
    "visa_sponsorship"
]:

    if possible_column in jobs.columns:

        sponsorship_column = (
            possible_column
        )

        break


if sponsorship_column:

    sponsorship_values = sorted(
        jobs[sponsorship_column]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_sponsorship = (
        st.sidebar.multiselect(
            "Sponsorship",
            sponsorship_values
        )
    )

else:

    selected_sponsorship = []


# ============================================================
# APPLY FILTERS
# ============================================================

filtered_jobs = jobs.copy()


if search_text:

    search_lower = (
        search_text
        .strip()
        .lower()
    )

    title_series = (
        safe_column(
            filtered_jobs,
            "job_title"
        )
        .astype(str)
        .str.lower()
    )

    company_series = (
        safe_column(
            filtered_jobs,
            "company"
        )
        .astype(str)
        .str.lower()
    )

    search_mask = (
        title_series.str.contains(
            search_lower,
            na=False,
            regex=False
        )
        |
        company_series.str.contains(
            search_lower,
            na=False,
            regex=False
        )
    )

    filtered_jobs = (
        filtered_jobs[
            search_mask
        ]
    )


if selected_locations:

    filtered_jobs = (
        filtered_jobs[
            filtered_jobs[
                "location"
            ].isin(
                selected_locations
            )
        ]
    )


if selected_job_types:

    filtered_jobs = (
        filtered_jobs[
            filtered_jobs[
                "job_type"
            ]
            .astype(str)
            .isin(
                selected_job_types
            )
        ]
    )


if selected_statuses:

    filtered_jobs = (
        filtered_jobs[
            filtered_jobs[
                "application_status"
            ].isin(
                selected_statuses
            )
        ]
    )


filtered_jobs = (
    filtered_jobs[
        filtered_jobs[
            "match_score"
        ] >= minimum_score
    ]
)


if (
    sponsorship_column
    and selected_sponsorship
):

    filtered_jobs = (
        filtered_jobs[
            filtered_jobs[
                sponsorship_column
            ]
            .astype(str)
            .isin(
                selected_sponsorship
            )
        ]
    )


filtered_jobs = (
    filtered_jobs
    .sort_values(
        by="match_score",
        ascending=False
    )
)


# ============================================================
# FILTER RESULT
# ============================================================

st.subheader(
    "Job Matches"
)

st.write(
    f"Showing **{len(filtered_jobs)}** "
    f"of **{len(jobs)}** jobs."
)


if filtered_jobs.empty:

    st.info(
        "No jobs match the current filters."
    )

    st.stop()


# ============================================================
# SEARCHABLE JOB TABLE
# ============================================================

st.subheader(
    "Tracker Table"
)

tracker_columns = [
    c
    for c in [
        "company",
        "job_title",
        "location",
        "job_type",
        sponsorship_column,
        "match_score",
        "application_status",
        "application_url"
    ]
    if c
    and c in filtered_jobs.columns
]


table_df = (
    filtered_jobs[
        tracker_columns
    ]
    .copy()
)


table_df = table_df.rename(
    columns={
        "company": "Company",
        "job_title": "Job Title",
        "location": "Location",
        "job_type": "Type",
        "sponsorship_status": "Sponsorship",
        "sponsorship": "Sponsorship",
        "visa_sponsorship": "Sponsorship",
        "match_score": "Match Score",
        "application_status": "Status",
        "application_url": "Apply",
    }
)


st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Apply": (
            st.column_config.LinkColumn(
                "Apply",
                display_text="Open posting"
            )
        )
    },
)


st.caption(
    "Use the filters in the sidebar to search the tracker. "
    "Use the job cards below to change application status."
)

st.divider()


# ============================================================
# JOB CARDS
# ============================================================

for _, job in filtered_jobs.iterrows():

    job_id = job.get(
        "id"
    )

    company = job.get(
        "company",
        "Unknown Company"
    )

    job_title = job.get(
        "job_title",
        "Unknown Position"
    )

    location = job.get(
        "location",
        "Unknown Location"
    )

    match_score = int(
        job.get(
            "match_score",
            0
        )
    )

    match_category = (
        get_match_category(
            match_score
        )
    )

    current_status = (
        normalize_status(
            job.get(
                "application_status",
                "New"
            )
        )
    )

    application_url = (
        job.get(
            "application_url",
            ""
        )
    )

    why_match = ""

    for possible_column in [
        "why_it_matches",
        "match_reason",
        "why_match"
    ]:

        if possible_column in jobs.columns:

            value = job.get(
                possible_column
            )

            if pd.notna(value):
                why_match = str(value)

            break


    sponsorship = (
        str(
            job.get(
                sponsorship_column,
                "Unknown"
            )
        )
        if sponsorship_column
        else "Unknown"
    )


    with st.container(
        border=True
    ):

        header_left, header_right = (
            st.columns(
                [4, 1]
            )
        )


        with header_left:

            st.subheader(
                f"{company} — {job_title}"
            )

            st.write(
                f"📍 {location}"
            )


        with header_right:

            st.metric(
                "Match Score",
                f"{match_score}/100"
            )


        detail_columns = (
            st.columns(3)
        )


        detail_columns[0].write(
            f"**Category:** "
            f"{match_category}"
        )


        detail_columns[1].write(
            f"**Sponsorship:** "
            f"{sponsorship}"
        )


        detail_columns[2].write(
            f"**Status:** "
            f"{current_status}"
        )


        if (
            sponsorship
            == "Work Authorization / Export Control Risk"
        ):

            st.warning(
                "This posting contains U.S.-person, "
                "ITAR, export-control, or related work-authorization "
                "language. Review the eligibility requirements "
                "carefully before applying."
            )


        if why_match:

            st.write(
                "**Why it matches:**"
            )

            st.write(
                why_match
            )


        with st.expander(
            "Resume Match Details"
        ):

            for label, column in [
                (
                    "Matched Skills",
                    "matched_resume_skills"
                ),
                (
                    "Relevant Experience",
                    "matched_resume_experience"
                ),
                (
                    "Missing Skills",
                    "missing_skills"
                ),
                (
                    "Potential Gaps",
                    "potential_gaps"
                ),
                (
                    "Suggested Resume Keywords",
                    "suggested_resume_keywords"
                ),
            ]:

                value = job.get(
                    column,
                    ""
                )

                if (
                    pd.notna(value)
                    and str(value).strip()
                ):

                    st.write(
                        f"**{label}:** {value}"
                    )


        action_left, action_middle = (
            st.columns(
                [1, 2]
            )
        )


        with action_left:

            if (
                isinstance(
                    application_url,
                    str
                )
                and
                application_url.startswith(
                    "http"
                )
            ):

                st.link_button(
                    "Apply",
                    application_url,
                    use_container_width=True
                )


        with action_middle:

            if (
                current_status
                not in statuses
            ):

                status_options = (
                    [current_status]
                    +
                    statuses
                )

            else:

                status_options = (
                    statuses
                )


            selected_index = (
                status_options.index(
                    current_status
                )
            )


            new_status = (
                st.selectbox(
                    "Application Status",
                    status_options,
                    index=selected_index,
                    key=(
                        f"status_{job_id}"
                    )
                )
            )


            if (
                new_status
                != current_status
            ):

                if (
                    job_id is None
                ):

                    st.error(
                        "This job does not have "
                        "a database ID."
                    )

                else:

                    update_application_status(
                        job_id,
                        new_status
                    )

                    st.success(
                        "Application status updated."
                    )

                    st.rerun()


# ============================================================
# DATABASE INFORMATION
# ============================================================

st.divider()


with st.expander(
    "Database Information"
):

    st.write(
        f"Database: `{DATABASE_PATH}`"
    )

    st.write(
        f"Jobs stored: {len(jobs)}"
    )

    st.write(
        "Database columns:"
    )

    st.code(
        "\n".join(
            get_table_columns()
        )
    )