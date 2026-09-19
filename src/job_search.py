from datetime import datetime, timezone
from html import unescape
from pathlib import Path
import re

import requests
import yaml


# ============================================================
# PROFILE
# ============================================================

def load_profile():
    """
    Load config/profile.yaml.
    """

    base_dir = Path(__file__).resolve().parent.parent
    config_path = base_dir / "config" / "profile.yaml"

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as file:
        return yaml.safe_load(file)


# ============================================================
# SHARED HELPERS
# ============================================================

REQUEST_HEADERS = {
    "User-Agent": "Student-Job-Search-Agent/2.0"
}


def strip_html(value):
    """
    Convert simple HTML job descriptions into readable plain text.
    """

    if not value:
        return ""

    text = re.sub(
        r"<(br|p|li|div|h[1-6])\b[^>]*>",
        "\n",
        str(value),
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = unescape(text)

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n\s*\n+",
        "\n",
        text
    )

    return text.strip()


def today_iso():
    return datetime.now(
        timezone.utc
    ).date().isoformat()


def normalize_job_type(value):
    """
    Keep source-provided employment type where possible.
    """

    if value is None:
        return "Unclear"

    value = str(value).strip()

    if not value:
        return "Unclear"

    return value


# ============================================================
# LEVER FETCHER
# ============================================================

def fetch_lever_jobs(
    company_token,
    company_name
):
    """
    Fetch public job postings from Lever.

    Example:
    https://api.lever.co/v0/postings/hermeus?mode=json
    """

    url = (
        f"https://api.lever.co/v0/postings/"
        f"{company_token}?mode=json"
    )

    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=20
        )

        response.raise_for_status()

    except requests.RequestException as error:

        print(
            f"Could not fetch Lever jobs from "
            f"{company_name}: {error}"
        )

        return []

    try:
        data = response.json()

    except ValueError:

        print(
            f"Invalid Lever JSON response from "
            f"{company_name}."
        )

        return []

    jobs = []

    for job in data:

        categories = (
            job.get(
                "categories",
                {}
            )
            or {}
        )

        description_parts = [
            job.get(
                "descriptionPlain",
                ""
            ),
            job.get(
                "additionalPlain",
                ""
            )
        ]

        description = " ".join(
            part
            for part in description_parts
            if part
        ).strip()

        normalized_job = {
            "company":
                company_name,

            "title":
                job.get(
                    "text",
                    "Unknown"
                ),

            "location":
                categories.get(
                    "location",
                    "Unknown"
                ),

            "job_type":
                normalize_job_type(
                    categories.get(
                        "commitment"
                    )
                ),

            "team":
                categories.get(
                    "team",
                    ""
                ),

            "department":
                categories.get(
                    "department",
                    ""
                ),

            "workplace_type":
                job.get(
                    "workplaceType",
                    ""
                ),

            "posting_date":
                None,

            "description":
                description,

            "required_skills":
                [],

            "experience_requirements":
                [],

            "salary":
                None,

            "sponsorship":
                "Sponsorship Unclear",

            "application_url":
                job.get(
                    "hostedUrl"
                ),

            "source":
                "Lever",

            "date_found":
                today_iso(),
        }

        if normalized_job[
            "application_url"
        ]:

            jobs.append(
                normalized_job
            )

    return jobs


# ============================================================
# GREENHOUSE FETCHER
# ============================================================

def fetch_greenhouse_jobs(
    board_token,
    company_name
):
    """
    Fetch public jobs from a Greenhouse job board.

    Public endpoint:
    https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
    """

    url = (
        "https://boards-api.greenhouse.io/"
        f"v1/boards/{board_token}/jobs"
    )

    params = {
        "content": "true"
    }

    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            params=params,
            timeout=20
        )

        response.raise_for_status()

    except requests.RequestException as error:

        print(
            f"Could not fetch Greenhouse jobs from "
            f"{company_name}: {error}"
        )

        return []

    try:
        payload = response.json()

    except ValueError:

        print(
            f"Invalid Greenhouse JSON response from "
            f"{company_name}."
        )

        return []

    jobs = []

    for job in payload.get(
        "jobs",
        []
    ):

        location_data = (
            job.get(
                "location",
                {}
            )
            or {}
        )

        departments = (
            job.get(
                "departments",
                []
            )
            or []
        )

        department_names = [
            item.get(
                "name"
            )
            for item in departments
            if item.get(
                "name"
            )
        ]

        offices = (
            job.get(
                "offices",
                []
            )
            or []
        )

        office_names = [
            item.get(
                "name"
            )
            for item in offices
            if item.get(
                "name"
            )
        ]

        metadata = (
            job.get(
                "metadata",
                []
            )
            or []
        )

        metadata_text = " | ".join(
            str(item.get("value"))
            for item in metadata
            if item.get("value")
        )

        description = strip_html(
            job.get(
                "content",
                ""
            )
        )

        if metadata_text:
            description = (
                f"{description}\n{metadata_text}"
            ).strip()

        normalized_job = {
            "company":
                company_name,

            "title":
                job.get(
                    "title",
                    "Unknown"
                ),

            "location":
                location_data.get(
                    "name",
                    "Unknown"
                ),

            "job_type":
                "Unclear",

            "team":
                ", ".join(
                    office_names
                ),

            "department":
                ", ".join(
                    department_names
                ),

            "workplace_type":
                "",

            "posting_date":
                job.get(
                    "updated_at"
                ),

            "description":
                description,

            "required_skills":
                [],

            "experience_requirements":
                [],

            "salary":
                None,

            "sponsorship":
                "Sponsorship Unclear",

            "application_url":
                job.get(
                    "absolute_url"
                ),

            "source":
                "Greenhouse",

            "date_found":
                today_iso(),
        }

        if normalized_job[
            "application_url"
        ]:

            jobs.append(
                normalized_job
            )

    return jobs


# ============================================================
# ASHBY FETCHER
# ============================================================

def fetch_ashby_jobs(
    board_name,
    company_name
):
    """
    Fetch public listed jobs from an Ashby hosted job board.

    Public endpoint:
    https://api.ashbyhq.com/posting-api/job-board/{board_name}
    """

    url = (
        "https://api.ashbyhq.com/"
        f"posting-api/job-board/{board_name}"
    )

    params = {
        "includeCompensation": "true"
    }

    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            params=params,
            timeout=20
        )

        response.raise_for_status()

    except requests.RequestException as error:

        print(
            f"Could not fetch Ashby jobs from "
            f"{company_name}: {error}"
        )

        return []

    try:
        payload = response.json()

    except ValueError:

        print(
            f"Invalid Ashby JSON response from "
            f"{company_name}."
        )

        return []

    jobs = []

    for job in payload.get(
        "jobs",
        []
    ):

        if job.get(
            "isListed"
        ) is False:
            continue

        compensation = (
            job.get(
                "compensation",
                {}
            )
            or {}
        )

        salary = (
            compensation.get(
                "scrapeableCompensationSalarySummary"
            )
            or compensation.get(
                "compensationTierSummary"
            )
        )

        description = (
            job.get(
                "descriptionPlain"
            )
            or strip_html(
                job.get(
                    "descriptionHtml",
                    ""
                )
            )
            or strip_html(
                job.get(
                    "description",
                    ""
                )
            )
        )

        location_type = (
            job.get(
                "locationType"
            )
            or ""
        )

        application_url = (
            job.get(
                "applyUrl"
            )
            or job.get(
                "jobUrl"
            )
        )

        normalized_job = {
            "company":
                company_name,

            "title":
                job.get(
                    "title",
                    "Unknown"
                ),

            "location":
                job.get(
                    "location",
                    "Unknown"
                ),

            "job_type":
                normalize_job_type(
                    job.get(
                        "employmentType"
                    )
                ),

            "team":
                job.get(
                    "team",
                    ""
                )
                or "",

            "department":
                job.get(
                    "department",
                    ""
                )
                or "",

            "workplace_type":
                location_type,

            "posting_date":
                (
                    job.get(
                        "publishedAt"
                    )
                    or job.get(
                        "publishedDate"
                    )
                ),

            "description":
                description,

            "required_skills":
                [],

            "experience_requirements":
                [],

            "salary":
                salary,

            "sponsorship":
                "Sponsorship Unclear",

            "application_url":
                application_url,

            "source":
                "Ashby",

            "date_found":
                today_iso(),
        }

        if normalized_job[
            "application_url"
        ]:

            jobs.append(
                normalized_job
            )

    return jobs


# ============================================================
# DEFAULT PUBLIC SOURCES
# ============================================================

DEFAULT_LEVER_SOURCES = [
    {"company": "Hermeus", "token": "hermeus"},
    {"company": "OpenX", "token": "openx"},
    {"company": "CIM Group", "token": "cimgroup"},
    {"company": "GHJ", "token": "ghj"},
    {"company": "Too Lost", "token": "too-lost"},
    {"company": "Bellwether", "token": "bellwetheram-2"},
    {"company": "Fi", "token": "fi"},
    {"company": "Wealthfront", "token": "wealthfront"},
    {"company": "CAI", "token": "cagents"},
    {"company": "Hot Topic & BoxLunch", "token": "hottopic"},
    {"company": "Nextech", "token": "nextech"},
    {"company": "Versana", "token": "Versana"},
    {"company": "e.l.f. Beauty", "token": "elfbeauty"},
]


DEFAULT_GREENHOUSE_SOURCES = [
    {"company": "Philz Coffee", "token": "philzcoffeecareers"},
    {"company": "General Matter", "token": "generalmatter"},
    {"company": "Metropolis", "token": "metropolis"},
    {"company": "SpaceX", "token": "spacex"},
    {"company": "Canonical", "token": "canonical"},
    {"company": "Anduril Industries", "token": "andurilindustries"},
    {"company": "Twitch", "token": "twitch"},
    {"company": "TEGNA", "token": "tegnainc"},
    {"company": "Glydways", "token": "glydways"},
    {"company": "Jordan Park Group", "token": "jordanparkgroup"},
]


DEFAULT_ASHBY_SOURCES = [
    {"company": "Apex", "board": "apex-technology-inc"},
    {"company": "Temporal", "board": "temporal"},
    {"company": "Instructure", "board": "instructure"},
    {"company": "Infinity Constellation", "board": "infinity-constellation"},
    {"company": "Coder", "board": "coder"},
    {"company": "Reframe Systems", "board": "reframesystems"},
    {"company": "Compa", "board": "compa"},
    {"company": "OpenGov", "board": "opengov"},
    {"company": "Hims & Hers", "board": "hims-and-hers"},
    {"company": "Limble", "board": "limble"},
    {"company": "Whatnot", "board": "whatnot"},
]


# ============================================================
# SOURCE CONFIGURATION
# ============================================================

def get_lever_sources(profile):
    configured_sources = (
        profile
        .get(
            "job_sources",
            {}
        )
        .get(
            "lever",
            []
        )
    )

    if configured_sources:
        return configured_sources

    return DEFAULT_LEVER_SOURCES


def get_greenhouse_sources(profile):
    configured_sources = (
        profile
        .get(
            "job_sources",
            {}
        )
        .get(
            "greenhouse",
            []
        )
    )

    if configured_sources:
        return configured_sources

    return DEFAULT_GREENHOUSE_SOURCES


def get_ashby_sources(profile):
    configured_sources = (
        profile
        .get(
            "job_sources",
            {}
        )
        .get(
            "ashby",
            []
        )
    )

    if configured_sources:
        return configured_sources

    return DEFAULT_ASHBY_SOURCES


# ============================================================
# SEARCH EACH SOURCE TYPE
# ============================================================

def search_all_lever_only(
    profile
):
    all_jobs = []

    sources = get_lever_sources(
        profile
    )

    print()
    print(
        "=== Searching Lever Job Sources ==="
    )
    print()

    print(
        f"Companies configured: "
        f"{len(sources)}"
    )

    print()

    successful = 0
    failed = 0

    for source in sources:

        company = source.get(
            "company"
        )

        token = source.get(
            "token"
        )

        if not company or not token:
            print(
                "Skipping invalid Lever source."
            )

            failed += 1
            continue

        print(
            f"Searching {company}..."
        )

        company_jobs = fetch_lever_jobs(
            company_token=token,
            company_name=company
        )

        if company_jobs:
            successful += 1

            print(
                f"Found {len(company_jobs)} "
                f"jobs from {company}."
            )

        else:
            failed += 1

            print(
                f"No jobs returned "
                f"from {company}."
            )

        print()

        all_jobs.extend(
            company_jobs
        )

    print(
        "Lever summary:"
    )

    print(
        f"- Successful companies: "
        f"{successful}"
    )

    print(
        f"- Failed / empty companies: "
        f"{failed}"
    )

    print(
        f"- Lever jobs discovered: "
        f"{len(all_jobs)}"
    )

    return all_jobs


def search_all_greenhouse_companies(
    profile
):
    all_jobs = []

    sources = get_greenhouse_sources(
        profile
    )

    print()
    print(
        "=== Searching Greenhouse Job Sources ==="
    )
    print()

    print(
        f"Companies configured: "
        f"{len(sources)}"
    )

    print()

    successful = 0
    failed = 0

    for source in sources:

        company = source.get(
            "company"
        )

        token = source.get(
            "token"
        )

        if not company or not token:
            print(
                "Skipping invalid Greenhouse source."
            )

            failed += 1
            continue

        print(
            f"Searching {company}..."
        )

        company_jobs = fetch_greenhouse_jobs(
            board_token=token,
            company_name=company
        )

        if company_jobs:
            successful += 1

            print(
                f"Found {len(company_jobs)} "
                f"jobs from {company}."
            )

        else:
            failed += 1

            print(
                f"No jobs returned "
                f"from {company}."
            )

        print()

        all_jobs.extend(
            company_jobs
        )

    print(
        "Greenhouse summary:"
    )

    print(
        f"- Successful companies: "
        f"{successful}"
    )

    print(
        f"- Failed / empty companies: "
        f"{failed}"
    )

    print(
        f"- Greenhouse jobs discovered: "
        f"{len(all_jobs)}"
    )

    return all_jobs


def search_all_ashby_companies(
    profile
):
    all_jobs = []

    sources = get_ashby_sources(
        profile
    )

    print()
    print(
        "=== Searching Ashby Job Sources ==="
    )
    print()

    print(
        f"Companies configured: "
        f"{len(sources)}"
    )

    print()

    successful = 0
    failed = 0

    for source in sources:

        company = source.get(
            "company"
        )

        board = (
            source.get(
                "board"
            )
            or source.get(
                "token"
            )
        )

        if not company or not board:
            print(
                "Skipping invalid Ashby source."
            )

            failed += 1
            continue

        print(
            f"Searching {company}..."
        )

        company_jobs = fetch_ashby_jobs(
            board_name=board,
            company_name=company
        )

        if company_jobs:
            successful += 1

            print(
                f"Found {len(company_jobs)} "
                f"jobs from {company}."
            )

        else:
            failed += 1

            print(
                f"No jobs returned "
                f"from {company}."
            )

        print()

        all_jobs.extend(
            company_jobs
        )

    print(
        "Ashby summary:"
    )

    print(
        f"- Successful companies: "
        f"{successful}"
    )

    print(
        f"- Failed / empty companies: "
        f"{failed}"
    )

    print(
        f"- Ashby jobs discovered: "
        f"{len(all_jobs)}"
    )

    return all_jobs


# ============================================================
# MULTI-SOURCE SEARCH
# ============================================================

def search_all_sources(
    profile
):
    """
    Search all configured public ATS sources.

    Current source adapters:
    - Lever
    - Greenhouse
    - Ashby
    """

    print()
    print(
        "=========================================="
    )
    print(
        "=== Multi-Source Job Search Starting ==="
    )
    print(
        "=========================================="
    )

    lever_jobs = search_all_lever_only(
        profile
    )

    greenhouse_jobs = (
        search_all_greenhouse_companies(
            profile
        )
    )

    ashby_jobs = search_all_ashby_companies(
        profile
    )

    all_jobs = (
        lever_jobs
        + greenhouse_jobs
        + ashby_jobs
    )

    print()
    print(
        "=== Multi-Source Search Summary ==="
    )

    print(
        f"Lever jobs: "
        f"{len(lever_jobs)}"
    )

    print(
        f"Greenhouse jobs: "
        f"{len(greenhouse_jobs)}"
    )

    print(
        f"Ashby jobs: "
        f"{len(ashby_jobs)}"
    )

    print(
        f"Raw jobs discovered: "
        f"{len(all_jobs)}"
    )

    return all_jobs


def search_all_lever_companies(
    profile
):
    """
    Backward-compatible wrapper.

    Your existing main.py already imports this function.
    It now returns Lever + Greenhouse + Ashby jobs so the
    rest of the existing Step 3-7 pipeline does not need
    to be changed.
    """

    return search_all_sources(
        profile
    )


# ============================================================
# DEDUPLICATION
# ============================================================

def remove_duplicate_jobs(
    jobs
):
    """
    Remove duplicate jobs.

    Primary key:
    - normalized application URL

    Secondary fallback:
    - company + title + location
    """

    unique_jobs = []
    seen_urls = set()
    seen_signatures = set()

    for job in jobs:

        url = job.get(
            "application_url"
        )

        company = str(
            job.get(
                "company",
                ""
            )
        ).strip().lower()

        title = str(
            job.get(
                "title",
                ""
            )
        ).strip().lower()

        location = str(
            job.get(
                "location",
                ""
            )
        ).strip().lower()

        signature = (
            company,
            title,
            location
        )

        normalized_url = ""

        if url:
            normalized_url = (
                str(url)
                .strip()
                .rstrip("/")
                .split("?")[0]
            )

        if (
            normalized_url
            and normalized_url
            in seen_urls
        ):
            continue

        if signature in seen_signatures:
            continue

        if normalized_url:
            seen_urls.add(
                normalized_url
            )

        seen_signatures.add(
            signature
        )

        unique_jobs.append(
            job
        )

    return unique_jobs


# ============================================================
# DISPLAY
# ============================================================

def display_jobs(
    jobs,
    limit=20
):
    """
    Display sample jobs for testing.
    """

    print()
    print(
        "=== Job Search Results ==="
    )
    print()

    print(
        f"Total jobs found: "
        f"{len(jobs)}"
    )

    print(
        "=" * 75
    )

    for job in jobs[:limit]:

        print(
            f"Company:    "
            f"{job.get('company')}"
        )

        print(
            f"Title:      "
            f"{job.get('title')}"
        )

        print(
            f"Location:   "
            f"{job.get('location')}"
        )

        print(
            f"Type:       "
            f"{job.get('job_type')}"
        )

        print(
            f"Department: "
            f"{job.get('department')}"
        )

        print(
            f"Team:       "
            f"{job.get('team')}"
        )

        print(
            f"Source:     "
            f"{job.get('source')}"
        )

        print(
            f"Apply:      "
            f"{job.get('application_url')}"
        )

        print(
            "-" * 75
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=== AI Job Search Agent ==="
    )

    profile = load_profile()

    jobs = search_all_sources(
        profile
    )

    jobs = remove_duplicate_jobs(
        jobs
    )

    print()

    print(
        f"Unique jobs after "
        f"deduplication: "
        f"{len(jobs)}"
    )

    display_jobs(
        jobs,
        limit=30
    )


if __name__ == "__main__":
    main()
