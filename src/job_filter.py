import re
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

REQUEST_HEADERS = {"User-Agent": "Student-Job-Search-Agent/2.0"}

EXCLUDED_COMPANIES = {
    "spacex",
    "anduril",
    "anduril industries",
}


def load_profile():
    """
    Load job search profile from config/profile.yaml.
    """

    base_dir = Path(__file__).resolve().parent.parent
    config_path = base_dir / "config" / "profile.yaml"

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as file:
        return yaml.safe_load(file)


def normalize_text(value):
    """
    Convert text to lowercase for easier matching.
    """

    if value is None:
        return ""

    return str(value).lower().strip()


def title_matches_target_role(job_title, target_roles):
    """
    Check whether a job title is reasonably related
    to one of the user's target roles.
    """

    title = normalize_text(job_title)

    if not title:
        return False

    target_keywords = []

    for role in target_roles:
        role_lower = normalize_text(role)

        target_keywords.extend(
            word
            for word in role_lower.split()
            if len(word) >= 4
        )

    finance_keywords = [
        "finance",
        "financial",
        "investment",
        "research",
        "risk",
        "quantitative",
        "quant",
        "business",
        "data",
        "analytics",
        "analyst",
        "strategy",
        "valuation",
        "corporate development",
        "fp&a",
        "treasury"
    ]

    all_keywords = set(
        target_keywords + finance_keywords
    )

    return any(
        keyword in title
        for keyword in all_keywords
    )


def extract_experience_requirement(job):
    """Return (minimum_years, maximum_years) for explicit experience requirements."""
    text = normalize_text(job.get("description"))
    if not text:
        return None, None

    # Explicit ranges: 0-3 years, 1 to 3 years, 2–4 years, etc.
    range_pattern = (
        r"(\d+)\s*(?:-|–|—|to)\s*(\d+)\s*years?"
        r"(?:\s+of)?(?:\s+(?:relevant|professional|work|finance|financial|related))?"
        r"\s*(?:experience)?"
    )
    ranges = [(int(a), int(b)) for a, b in re.findall(range_pattern, text)]
    if ranges:
        # Use the strictest explicit range found in the posting.
        return max(a for a, _ in ranges), max(b for _, b in ranges)

    minimum_patterns = [
        r"(?:minimum(?:\s+of)?|at\s+least|requires?|required|have)\s+(\d+)\+?\s*years?",
        r"(\d+)\+\s*years?(?:\s+of)?(?:\s+(?:relevant|professional|work|finance|financial|related))?\s*(?:experience)?",
    ]
    values = []
    for pattern in minimum_patterns:
        values.extend(int(x) for x in re.findall(pattern, text))

    return (max(values), None) if values else (None, None)


def clearly_too_senior(job, profile=None):
    """Reject senior titles or experience requirements outside the 0-3 year target."""
    title = normalize_text(job.get("title"))

    senior_title_terms = [
        "senior", "sr.", "staff", "principal", "director",
        "vice president", "vp ", "vp,", "head of", "manager",
        "lead ", "chief ", "executive", "partner"
    ]
    if any(term in title for term in senior_title_terms):
        return True

    minimum_years, maximum_years = extract_experience_requirement(job)

    # Reject explicit ranges that extend beyond 3 years, e.g. 2-4 or 3-5.
    if maximum_years is not None and maximum_years > 3:
        return True

    # Reject open-ended requirements beginning at 4+ years.
    if minimum_years is not None and minimum_years >= 4:
        return True

    return False


def excluded_sensitive_industry(job):
    """Reject defense/military/weapons/nuclear roles; commercial aerospace alone is allowed."""
    text = normalize_text(
        f"{job.get('company', '')} {job.get('title', '')} {job.get('description', '')}"
    )
    sensitive_terms = [
        "defense technology", "defense tech", "defense contractor",
        "defence technology", "defence contractor",
        "military technology", "military systems", "military contractor",
        "weapons systems", "weapon systems", "weapons technology", "munitions",
        "nuclear energy", "nuclear power", "nuclear reactor",
        "nuclear engineering", "nuclear technology", "nuclear weapons",
    ]
    return any(term in text for term in sensitive_terms)


def requires_immediate_start(job):
    """Reject postings that explicitly require an immediate/ASAP start."""
    text = normalize_text(f"{job.get('title', '')} {job.get('description', '')}")
    immediate_start_terms = [
        "immediate start", "start immediately", "starting immediately",
        "available immediately", "immediate availability", "immediately available",
        "asap start", "start asap", "start as soon as possible",
        "immediate hire", "hiring immediately",
    ]
    return any(term in text for term in immediate_start_terms)

def job_type_matches(job, profile):
    """
    Check internship / full-time preferences.
    """

    preferred_types = (
        profile
        .get("job_preferences", {})
        .get("job_types", [])
    )

    if not preferred_types:
        return True

    job_type = normalize_text(job.get("job_type"))

    if not job_type or job_type == "unclear":
        return True

    preferred_types_normalized = [
        normalize_text(item).replace("_", "-")
        for item in preferred_types
    ]

    aliases = {
        "full-time": [
            "full-time",
            "full time",
            "fulltime"
        ],
        "internship": [
            "internship",
            "intern"
        ]
    }

    for preferred_type in preferred_types_normalized:

        if preferred_type == "full-time":
            if any(
                value in job_type
                for value in aliases["full-time"]
            ):
                return True

        elif preferred_type == "internship":
            if any(
                value in job_type
                for value in aliases["internship"]
            ):
                return True

        elif preferred_type in job_type:
            return True

    return False


def location_matches(job, profile):
    """
    Apply a light location filter.

    United States in the profile means US-based
    jobs should generally remain eligible.
    """

    preferred_locations = profile.get(
        "locations",
        []
    )

    if not preferred_locations:
        return True

    job_location = normalize_text(
        job.get("location")
    )

    if not job_location:
        return True

    preferred_locations_normalized = [
        normalize_text(location)
        for location in preferred_locations
    ]

    if "united states" in preferred_locations_normalized:
        return True

    for location in preferred_locations_normalized:
        if location in job_location:
            return True

    return False



def classify_sponsorship(job):
    """
    Classify sponsorship using only explicit language
    found in the job posting.

    Do not guess based on company size.
    """
    text = normalize_text(
        f"{job.get('title', '')} "
        f"{job.get('description', '')}"
    )

    likely_no_sponsor_terms = [
        "no visa sponsorship",
        "unable to sponsor",
        "cannot sponsor",
        "will not sponsor",
        "not able to sponsor",
        "without sponsorship",
        "without future sponsorship",
        "no sponsorship available",
        "sponsorship is not available",
        "do not provide sponsorship",
        "does not provide sponsorship",
        "not eligible for sponsorship",
        "no current or future sponsorship",
        "without current or future sponsorship",
        "without current or future visa sponsorship",
        "without employer sponsorship now or in the future",
        "unrestricted work authorization",
        "permanent work authorization",
        "must not require sponsorship",
        "not provide visa sponsorship",
        "not offer visa sponsorship",
    ]

    likely_sponsor_terms = [
        "visa sponsorship available",
        "sponsorship available",
        "will sponsor",
        "we sponsor",
        "h-1b sponsorship",
        "h1b sponsorship",
        "employment sponsorship",
    ]

    # Export-control / ITAR restrictions.
    us_person_terms = [
        "u.s. citizen or national",
        "us citizen or national",
        "u.s. lawful permanent resident",
        "lawful permanent resident",
        "green card holder",
        "green cardholder",
        "refugee or asylee",
        "refugee, or asylee",
    ]

    government_authorization_terms = [
        "eligible to obtain the required authorizations",
        "eligible to obtain required authorizations",
        "eligible to obtain the required authorization",
        "eligible to obtain required authorization",
        "obtain the required authorizations",
        "obtain required authorizations",
        "obtain the required authorization",
        "obtain required authorization",
    ]

    has_us_person_restriction = any(
        term in text
        for term in us_person_terms
    )

    allows_government_authorization = any(
        term in text
        for term in government_authorization_terms
    )

    if has_us_person_restriction:
        if allows_government_authorization:
            return "Work Authorization / Export Control Risk"

        return "Likely Does Not Sponsor"

    for term in likely_no_sponsor_terms:
        if term in text:
            return "Likely Does Not Sponsor"

    for term in likely_sponsor_terms:
        if term in text:
            return "Likely Sponsors"

    return "Sponsorship Unclear"


def filter_job(job, profile):
    """
    Decide whether a single job should remain.
    """

    company = normalize_text(job.get("company"))
    if any(company == excluded or company.startswith(excluded + " ") or company.startswith(excluded + ",") or company.startswith(excluded + ".") for excluded in EXCLUDED_COMPANIES):
        return False, "Company excluded"

    target_roles = profile.get(
        "target_roles",
        []
    )

    # Sponsorship is a hard eligibility gate for this candidate.
    if (
        profile.get("candidate", {}).get("requires_future_sponsorship", False)
        and job.get("sponsorship") == "Likely Does Not Sponsor"
    ):
        return False, "Explicitly does not sponsor"

    if clearly_too_senior(job, profile):
        return False, "Experience requirement outside 0-3 year target"

    if excluded_sensitive_industry(job):
        return False, "Excluded sensitive industry"

    if requires_immediate_start(job):
        return False, "Immediate-start role"

    if not title_matches_target_role(
        job.get("title"),
        target_roles
    ):
        return False, "Job function does not match"

    if not job_type_matches(job, profile):
        return False, "Job type does not match"

    if not location_matches(job, profile):
        return False, "Location does not match"

    return True, "Passed filter"


def verify_sponsorship_on_application_page(job, timeout=8):
    """Re-check an unclear job against its real application page.

    This uses an ordinary GET request only. It does not bypass login, CAPTCHA,
    robots/access controls, or rate limits. Network/access failures leave the
    status Unclear rather than guessing.
    """
    if job.get("sponsorship") != "Sponsorship Unclear":
        return job.get("sponsorship")

    url = (job.get("application_url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "Sponsorship Unclear"

    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return "Sponsorship Unclear"

    # HTML tags do not matter for phrase matching; whitespace normalization helps.
    page_text = re.sub(r"<[^>]+>", " ", response.text or "")
    page_text = re.sub(r"\s+", " ", page_text)
    page_job = {"title": job.get("title", ""), "description": page_text}
    return classify_sponsorship(page_job)


def filter_jobs(jobs, profile):
    """
    Filter jobs efficiently.

    Pipeline:
    1. Classify sponsorship from existing job data.
    2. Run fast local eligibility filters first.
    3. Only verify application pages for locally eligible jobs
       whose sponsorship is still unclear.
    4. Re-apply the hard sponsorship gate after verification.
    """

    filtered_jobs = []
    removed_jobs = []
    local_candidates = []

    verify_page = profile.get("search", {}).get(
        "verify_application_page_sponsorship", True
    )

    total_jobs = len(jobs)

    print(f"Basic local filtering started: {total_jobs} jobs")

    # Phase 1: fast local filtering only.
    # No network requests are made here.
    for job in jobs:
        job = job.copy()

        # Classify sponsorship using the job data we already have.
        job["sponsorship"] = classify_sponsorship(job)

        keep, reason = filter_job(
            job,
            profile
        )

        job["filter_reason"] = reason

        if keep:
            local_candidates.append(job)
        else:
            removed_jobs.append(job)

    print(
        f"Basic local filtering complete: "
        f"{total_jobs} -> {len(local_candidates)} candidates"
    )

    # Phase 2: verify sponsorship only for jobs that survived
    # the fast local filters.
    unclear_jobs = sum(
        1
        for job in local_candidates
        if job.get("sponsorship") == "Sponsorship Unclear"
    )

    if verify_page:
        print(
            f"Sponsorship verification needed for "
            f"{unclear_jobs} unclear candidates"
        )
    else:
        print("Application-page sponsorship verification disabled")

    checked = 0

    for job in local_candidates:

        if (
            verify_page
            and job.get("sponsorship") == "Sponsorship Unclear"
        ):
            checked += 1

            if (
                checked == 1
                or checked % 25 == 0
                or checked == unclear_jobs
            ):
                print(
                    f"Sponsorship page verification: "
                    f"{checked}/{unclear_jobs}"
                )

            job["sponsorship"] = (
                verify_sponsorship_on_application_page(job)
            )

        # Re-run the filter because page verification may have
        # changed an unclear job to Likely Does Not Sponsor.
        keep, reason = filter_job(
            job,
            profile
        )

        job["filter_reason"] = reason

        if keep:
            filtered_jobs.append(job)
        else:
            removed_jobs.append(job)

    print(
        f"Final filtering complete: "
        f"{len(filtered_jobs)} jobs retained"
    )

    print(
        f"Removed during filtering: "
        f"{len(removed_jobs)} jobs"
    )

    return filtered_jobs, removed_jobs


def display_filtered_jobs(
    filtered_jobs,
    removed_jobs,
    limit=20
):
    """
    Print filtering results for testing.
    """

    print()
    print("=== Job Filter Results ===")
    print()

    print(
        f"Jobs kept: {len(filtered_jobs)}"
    )

    print(
        f"Jobs removed: {len(removed_jobs)}"
    )

    print("=" * 70)

    for job in filtered_jobs[:limit]:

        print(f"Company:     {job['company']}")
        print(f"Title:       {job['title']}")
        print(f"Location:    {job['location']}")
        print(f"Type:        {job['job_type']}")
        print(f"Sponsorship: {job['sponsorship']}")
        print(f"Apply:       {job['application_url']}")

        print("-" * 70)


if __name__ == "__main__":

    from job_search import (
        load_profile,
        search_all_lever_companies
    )

    profile = load_profile()

    jobs = search_all_lever_companies(
        profile
    )

    filtered_jobs, removed_jobs = filter_jobs(
        jobs,
        profile
    )

    display_filtered_jobs(
        filtered_jobs,
        removed_jobs,
        limit=20
    )