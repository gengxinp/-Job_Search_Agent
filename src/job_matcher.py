from datetime import datetime, timezone
import re

from resume_parser import parse_resume


# ============================================================
# BASIC HELPERS
# ============================================================

def normalize_text(value):
    if value is None:
        return ""
    return str(value).lower().strip()


def combined_job_text(job):
    return " ".join([
        normalize_text(job.get("title")),
        normalize_text(job.get("description")),
        normalize_text(job.get("location")),
    ])


# ============================================================
# LOCATION FILTER
# ============================================================

US_STATE_NAMES = [
    "alabama", "alaska", "arizona", "arkansas", "california",
    "colorado", "connecticut", "delaware", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas",
    "kentucky", "louisiana", "maine", "maryland", "massachusetts",
    "michigan", "minnesota", "mississippi", "missouri", "montana",
    "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota",
    "ohio", "oklahoma", "oregon", "pennsylvania",
    "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
    "district of columbia"
]


US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC"
}


US_CITY_TERMS = [
    "los angeles",
    "san francisco",
    "san diego",
    "new york",
    "chicago",
    "boston",
    "seattle",
    "austin",
    "dallas",
    "houston",
    "miami",
    "atlanta",
    "denver",
    "washington dc",
    "washington, dc",
    "philadelphia",
    "phoenix",
    "charlotte",
    "raleigh",
    "pittsburgh"
]


NON_US_TERMS = [
    "lagos",
    "nigeria",
    "budapest",
    "hungary",
    "london",
    "united kingdom",
    "uk",
    "canada",
    "toronto",
    "vancouver",
    "india",
    "bengaluru",
    "bangalore",
    "mumbai",
    "singapore",
    "australia",
    "sydney",
    "melbourne",
    "germany",
    "berlin",
    "france",
    "paris",
    "spain",
    "madrid",
    "netherlands",
    "amsterdam",
    "poland",
    "warsaw",
    "romania",
    "bucharest",
    "portugal",
    "lisbon",
    "mexico",
    "brazil",
    "colombia",
    "argentina",
    "philippines",
    "japan",
    "tokyo",
    "china",
    "hong kong",
    "taiwan",
    "south korea",
    "israel",
    "dubai",
    "united arab emirates"
]


def is_us_location(location):
    """
    Returns True only when the location appears to be
    in the United States or explicitly US-remote.
    """

    raw_location = str(location or "").strip()
    location_lower = raw_location.lower()

    if not location_lower:
        return False

    # Explicit US-wide language
    us_phrases = [
        "united states",
        "united states of america",
        "usa",
        "u.s.",
        "u.s.a.",
        "us remote",
        "remote - us",
        "remote, us",
        "remote us",
        "remote (us)",
        "remote - united states",
        "remote, united states",
    ]

    if any(term in location_lower for term in us_phrases):
        return True

    # Explicit foreign location
    if any(term in location_lower for term in NON_US_TERMS):
        return False

    # US state names
    if any(state in location_lower for state in US_STATE_NAMES):
        return True

    # Common US cities
    if any(city in location_lower for city in US_CITY_TERMS):
        return True

    # Detect state abbreviation in formats such as:
    # Los Angeles, CA
    # New York, NY
    state_matches = re.findall(
        r"(?:,\s*|\b)([A-Z]{2})(?:\b|$)",
        raw_location
    )

    if any(code in US_STATE_CODES for code in state_matches):
        return True

    # Plain "Remote" is ambiguous.
    # Do not assume it means United States.
    return False


def apply_us_location_filter(jobs):
    kept = []
    removed = []

    for job in jobs:
        if is_us_location(job.get("location")):
            kept.append(job)
        else:
            removed.append(job)

    return kept, removed


# ============================================================
# JOB FUNCTION / CAREER FIT
# ============================================================

def score_job_function(job, profile):
    """
    Maximum: 25

    Finance-oriented roles receive the strongest scores.
    Generic analyst roles receive lower scores.
    """

    title = normalize_text(job.get("title"))

    if not title:
        return 0

    # --------------------------------------------------------
    # Clearly irrelevant professional tracks
    # --------------------------------------------------------

    irrelevant_terms = [
        "software engineer",
        "software developer",
        "frontend engineer",
        "front end engineer",
        "backend engineer",
        "back end engineer",
        "full stack",
        "fullstack",
        "devops",
        "site reliability",
        "machine learning engineer",
        "data engineer",
        "electrical engineer",
        "mechanical engineer",
        "systems engineer",
        "avionics",
        "flight safety",
        "manufacturing engineer",
        "hardware engineer",
        "nurse",
        "physician",
        "medical",
        "clinical",
        "pharmacist",
        "attorney",
        "lawyer",
        "account executive",
        "sales representative",
        "customer success",
        "recruiter",
        "talent acquisition",
        "graphic designer",
        "product designer"
    ]

    if any(term in title for term in irrelevant_terms):
        return 0

    # --------------------------------------------------------
    # Seniority penalty
    # --------------------------------------------------------

    senior_terms = [
        "senior ",
        "sr. ",
        "sr ",
        "principal",
        "director",
        "vice president",
        "vp ",
        "head of",
        "chief ",
        "manager",
        "lead "
    ]

    senior_penalty = (
        8 if any(term in title for term in senior_terms)
        else 0
    )

    # --------------------------------------------------------
    # Highest-priority finance roles
    # --------------------------------------------------------

    tier_1 = [
        "financial analyst",
        "finance analyst",
        "fp&a analyst",
        "fp&a",
        "corporate finance analyst",
        "investment analyst",
        "investment banking analyst",
        "valuation analyst",
        "equity research analyst",
        "research analyst",
        "credit analyst",
        "portfolio analyst",
        "treasury analyst",
        "corporate development analyst",
        "strategic finance analyst"
    ]

    if any(term in title for term in tier_1):
        return max(25 - senior_penalty, 0)

    # --------------------------------------------------------
    # Strong finance-adjacent roles
    # --------------------------------------------------------

    tier_2 = [
        "risk analyst",
        "capital markets",
        "investment banking",
        "private equity",
        "venture capital",
        "corporate development",
        "financial planning",
        "financial strategy",
        "investment research",
        "asset management",
        "wealth management",
        "portfolio management",
        "credit research"
    ]

    if any(term in title for term in tier_2):
        return max(22 - senior_penalty, 0)

    # --------------------------------------------------------
    # Analytics / strategy roles
    # --------------------------------------------------------

    tier_3 = [
        "strategy analyst",
        "strategic analyst",
        "data analyst",
        "business intelligence analyst",
        "operations analyst",
        "pricing analyst",
        "revenue analyst",
        "commercial analyst"
    ]

    if any(term in title for term in tier_3):
        return max(17 - senior_penalty, 0)

    # Generic Business Analyst is intentionally lower.
    if "business analyst" in title:
        return max(13 - senior_penalty, 0)

    # Generic analyst
    if "analyst" in title:
        return max(10 - senior_penalty, 0)

    # Associate roles in relevant finance areas
    finance_terms = [
        "finance",
        "financial",
        "investment",
        "valuation",
        "portfolio",
        "treasury",
        "capital markets",
        "corporate development"
    ]

    if (
        "associate" in title
        and any(term in title for term in finance_terms)
    ):
        return max(15 - senior_penalty, 0)

    return 3


# ============================================================
# RESUME SKILLS
# ============================================================

def score_resume_skills(job, resume_data):
    """Maximum: 20. Combines exact resume-skill matches with finance-skill adjacency."""
    text = combined_job_text(job)
    resume_skills = resume_data.get("skills", [])
    if not text or not resume_skills:
        return 0, []

    skill_aliases = {
        "Python": ["python"], "SQL": ["sql"],
        "Excel": ["excel", "microsoft excel", "spreadsheet", "spreadsheets"],
        "PowerPoint": ["powerpoint", "microsoft powerpoint", "presentation", "presentations"],
        "Tableau": ["tableau"], "Power BI": ["power bi", "powerbi"],
        "R": ["r programming", "r language"],
        "Statistics": ["statistics", "statistical"],
        "Data Analytics": ["data analytics", "data analysis", "analytics", "business analytics"],
        "Financial Modeling": ["financial modeling", "financial modelling", "financial model", "financial models", "three statement model", "3-statement model"],
        "Valuation": ["valuation", "dcf", "discounted cash flow", "comparable company", "comparable companies", "precedent transaction", "trading comps"],
        "Capital IQ": ["capital iq", "s&p capital iq"], "Bloomberg": ["bloomberg"],
        "PitchBook": ["pitchbook"], "Machine Learning": ["machine learning"]
    }

    exact = []
    normalized_resume = {normalize_text(x): x for x in resume_skills}
    for skill in resume_skills:
        aliases = skill_aliases.get(skill, [normalize_text(skill)])
        if any(alias in text for alias in aliases):
            exact.append(skill)

    # Adjacent concepts are deliberately worth less than an exact skill match.
    adjacency = {
        "Financial Modeling": ["forecasting", "forecast", "budgeting", "budget", "scenario analysis", "financial planning", "fp&a", "variance analysis", "operating model", "long-range plan", "long range plan"],
        "Valuation": ["transaction analysis", "investment analysis", "returns analysis", "deal analysis", "corporate development", "m&a"],
        "Data Analytics": ["kpi", "kpis", "metrics", "dashboard", "reporting", "data-driven", "data driven", "trend analysis"],
        "Excel": ["financial model", "financial modeling", "forecasting", "budgeting", "spreadsheet model"]
    }
    adjacent = []
    for canonical, terms in adjacency.items():
        if canonical in resume_skills and canonical not in exact and any(term in text for term in terms):
            adjacent.append(canonical)

    exact = list(dict.fromkeys(exact))
    adjacent = list(dict.fromkeys(adjacent))
    weighted_hits = len(exact) + 0.5 * len(adjacent)
    if weighted_hits >= 6: score = 20
    elif weighted_hits >= 5: score = 18
    elif weighted_hits >= 4: score = 16
    elif weighted_hits >= 3: score = 13
    elif weighted_hits >= 2: score = 10
    elif weighted_hits >= 1: score = 6
    elif weighted_hits >= 0.5: score = 3
    else: score = 0

    matched = exact + [f"{x} (related)" for x in adjacent]
    return score, matched


# ============================================================
# RESUME EXPERIENCE
# ============================================================

def score_resume_experience(job, resume_data):
    """Maximum: 20. Rewards exact experience plus closely related finance work."""
    text = combined_job_text(job)
    experience_keywords = resume_data.get("experience_keywords", [])
    if not text or not experience_keywords:
        return 0, []

    aliases = {
        "Investment Banking": ["investment banking", "capital markets", "m&a", "mergers and acquisitions", "transaction advisory"],
        "Private Equity": ["private equity", "buyout", "portfolio company"],
        "Venture Capital": ["venture capital", "venture investing", "startup investing"],
        "Equity Research": ["equity research", "investment research", "securities research"],
        "Financial Analysis": ["financial analysis", "financial planning", "financial performance", "financial reporting", "fp&a", "forecasting", "budgeting", "variance analysis", "strategic finance", "corporate finance"],
        "Valuation": ["valuation", "dcf", "discounted cash flow", "comparable companies", "comps", "transaction analysis", "returns analysis"],
        "Due Diligence": ["due diligence", "diligence", "transaction diligence", "investment diligence"],
        "Market Research": ["market research", "market analysis", "industry research", "industry analysis", "competitive analysis", "competitive landscape"],
        "Data Analysis": ["data analysis", "analytics", "data analytics", "kpi", "kpis", "metrics", "dashboard", "trend analysis"],
        "Risk Analysis": ["risk analysis", "risk management", "risk assessment", "scenario analysis", "sensitivity analysis"]
    }

    exact = []
    for item in experience_keywords:
        item_aliases = aliases.get(item, [normalize_text(item)])
        if any(alias in text for alias in item_aliases):
            exact.append(item)
    exact = list(dict.fromkeys(exact))

    # Cross-functional finance relevance: only awarded when the resume actually
    # contains the anchor experience, preventing generic analyst jobs from inflating.
    related_rules = {
        "Financial Analysis": ["business partnering", "management reporting", "monthly close", "quarterly close", "planning cycle", "annual plan", "operating plan", "unit economics", "business case"],
        "Valuation": ["corporate development", "acquisition", "investment opportunity", "capital allocation"],
        "Due Diligence": ["deal execution", "transaction", "investment opportunity", "commercial diligence"],
        "Market Research": ["market sizing", "competitive intelligence", "industry trends", "market trends"],
        "Data Analysis": ["business intelligence", "performance metrics", "operational metrics", "reporting automation"]
    }
    related = []
    for item, terms in related_rules.items():
        if item in experience_keywords and item not in exact and any(term in text for term in terms):
            related.append(item)

    weighted_hits = len(exact) + 0.5 * len(related)
    if weighted_hits >= 4: score = 20
    elif weighted_hits >= 3: score = 18
    elif weighted_hits >= 2: score = 15
    elif weighted_hits >= 1: score = 10
    elif weighted_hits >= 0.5: score = 5
    else: score = 0

    matched = exact + [f"{x} (related)" for x in related]
    return score, matched


# ============================================================
# EXPERIENCE LEVEL
# ============================================================

def score_experience_level(job):
    """
    Maximum: 15
    """

    title = normalize_text(job.get("title"))
    description = normalize_text(job.get("description"))

    combined = f"{title} {description}"

    # Explicit senior title first
    senior_title_terms = [
        "senior ",
        "sr. ",
        "sr ",
        "principal",
        "director",
        "vice president",
        "vp ",
        "head of",
        "chief ",
        "manager",
        "lead "
    ]

    if any(term in title for term in senior_title_terms):
        return 1

    # Very high experience requirements
    high_experience_patterns = [
        r"\b7\+?\s*years",
        r"\b8\+?\s*years",
        r"\b9\+?\s*years",
        r"\b10\+?\s*years",
        r"\b6\+?\s*years"
    ]

    if any(
        re.search(pattern, combined)
        for pattern in high_experience_patterns
    ):
        return 1

    difficult_patterns = [
        r"\b5\+?\s*years",
        r"\b4\+?\s*years",
        r"\b4\s*-\s*6\s*years",
        r"\b5\s*-\s*7\s*years"
    ]

    if any(
        re.search(pattern, combined)
        for pattern in difficult_patterns
    ):
        return 4

    moderate_patterns = [
        r"\b3\+?\s*years",
        r"\b3\s*-\s*5\s*years"
    ]

    if any(
        re.search(pattern, combined)
        for pattern in moderate_patterns
    ):
        return 8

    reasonable_patterns = [
        r"\b2\+?\s*years",
        r"\b1\s*-\s*3\s*years",
        r"\b2\s*-\s*3\s*years"
    ]

    if any(
        re.search(pattern, combined)
        for pattern in reasonable_patterns
    ):
        return 12

    entry_terms = [
        "entry level",
        "entry-level",
        "new graduate",
        "new grad",
        "recent graduate",
        "recent grad",
        "early career",
        "0-1 years",
        "0 - 1 years",
        "0-2 years",
        "0 - 2 years",
        "1-2 years",
        "1 - 2 years",
        "1+ years"
    ]

    if any(term in combined for term in entry_terms):
        return 15

    # Analyst roles with no explicit years requirement
    if "analyst" in title:
        return 11

    return 8


# ============================================================
# EDUCATION
# ============================================================

def score_education(job, resume_data):
    """
    Maximum: 10
    """

    description = normalize_text(job.get("description"))

    resume_education = resume_data.get("education", [])

    has_bachelor = "Bachelor's degree" in resume_education
    has_master = "Master's degree" in resume_education

    if not description:
        return 8

    phd_required_terms = [
        "phd required",
        "ph.d. required",
        "doctorate required"
    ]

    if any(term in description for term in phd_required_terms):
        return 2

    master_terms = [
        "master's degree",
        "masters degree",
        "graduate degree",
        "mba"
    ]

    bachelor_terms = [
        "bachelor",
        "bachelor's degree",
        "bachelors degree",
        "undergraduate degree"
    ]

    if any(term in description for term in master_terms):
        return 10 if has_master else 5

    if any(term in description for term in bachelor_terms):
        return 10 if (has_bachelor or has_master) else 5

    return 8


# ============================================================
# SPONSORSHIP
# ============================================================

def score_sponsorship(job, profile):
    """
    Maximum: 5
    """

    requires_sponsorship = (
        profile
        .get("candidate", {})
        .get("requires_future_sponsorship", False)
    )

    if not requires_sponsorship:
        return 5

    sponsorship = normalize_text(job.get("sponsorship"))

    positive_terms = [
        "likely sponsors",
        "sponsorship available",
        "visa sponsorship available",
        "will sponsor"
    ]

    negative_terms = [
        "does not sponsor",
        "no sponsorship",
        "unable to sponsor",
        "cannot sponsor",
        "not sponsor",
        "without sponsorship",
        "without visa sponsorship"
    ]

    if any(term in sponsorship for term in negative_terms):
        return 0

    if any(term in sponsorship for term in positive_terms):
        return 5

    return 3


# ============================================================
# LOCATION SCORE
# ============================================================

def score_location(job, profile):
    """
    Maximum: 5.

    Non-US jobs should already have been removed.
    """

    location = normalize_text(job.get("location"))

    if not location:
        return 0

    # Highest preference
    top_locations = [
        "los angeles",
        "california",
        "new york"
    ]

    if any(term in location for term in top_locations):
        return 5

    if (
        "remote" in location
        and (
            "us" in location
            or "united states" in location
        )
    ):
        return 5

    # Any other confirmed US location
    if is_us_location(job.get("location")):
        return 4

    return 0


# ============================================================
# RECENCY
# ============================================================

def score_recency(job):
    """
    Maximum: 5
    """

    posting_date = job.get("posting_date")

    if not posting_date:
        return 3

    try:
        value = str(posting_date).replace("Z", "+00:00")

        posting_date_obj = datetime.fromisoformat(value)

        if posting_date_obj.tzinfo is None:
            posting_date_obj = posting_date_obj.replace(
                tzinfo=timezone.utc
            )

        today = datetime.now(timezone.utc)

        days_old = (today - posting_date_obj).days

    except (ValueError, TypeError):
        return 3

    if days_old <= 3:
        return 5

    if days_old <= 7:
        return 5

    if days_old <= 14:
        return 4

    if days_old <= 30:
        return 3

    if days_old <= 60:
        return 2

    return 1


# ============================================================
# HARD JOB RELEVANCE CHECK
# ============================================================

def is_career_relevant(job):
    """
    Prevent obviously unrelated jobs from entering the
    final ranked list.
    """

    title = normalize_text(job.get("title"))

    if not title:
        return False

    excluded = [
        "software engineer",
        "software developer",
        "frontend engineer",
        "backend engineer",
        "full stack engineer",
        "devops",
        "data engineer",
        "machine learning engineer",
        "electrical engineer",
        "mechanical engineer",
        "systems engineer",
        "avionics",
        "flight safety",
        "manufacturing engineer",
        "hardware engineer",
        "nurse",
        "physician",
        "clinical",
        "pharmacist",
        "account executive",
        "sales representative",
        "customer success",
        "recruiter",
        "talent acquisition",
        "graphic designer",
        "product designer"
    ]

    if any(term in title for term in excluded):
        return False

    relevant = [
        "analyst",
        "finance",
        "financial",
        "investment",
        "valuation",
        "research",
        "strategy",
        "strategic",
        "risk",
        "portfolio",
        "treasury",
        "capital markets",
        "corporate development",
        "private equity",
        "venture capital",
        "asset management",
        "wealth management"
    ]

    return any(term in title for term in relevant)


def apply_career_filter(jobs):
    kept = []
    removed = []

    for job in jobs:
        if is_career_relevant(job):
            kept.append(job)
        else:
            removed.append(job)

    return kept, removed


# ============================================================
# MATCH CATEGORY
# ============================================================

def get_match_category(score):
    if score >= 90:
        return "Excellent Match"

    if score >= 80:
        return "Strong Match"

    if score >= 70:
        return "Good Match"

    if score >= 60:
        return "Possible Match"

    return "Lower Priority"


# ============================================================
# MATCH REASON
# ============================================================

def build_match_reason(
    job,
    component_scores,
    matched_skills,
    matched_experience
):
    reasons = []

    if component_scores["job_function"] >= 22:
        reasons.append(
            "strong alignment with your target finance roles"
        )

    elif component_scores["job_function"] >= 15:
        reasons.append(
            "related analyst or finance-adjacent role"
        )

    if matched_skills:
        reasons.append(
            "matching resume skills: "
            + ", ".join(matched_skills[:5])
        )

    if matched_experience:
        reasons.append(
            "relevant resume experience: "
            + ", ".join(matched_experience[:4])
        )

    if component_scores["experience_level"] >= 12:
        reasons.append(
            "experience level appears appropriate"
        )

    if component_scores["education"] >= 9:
        reasons.append(
            "education appears compatible"
        )

    sponsorship = normalize_text(job.get("sponsorship"))

    if "likely sponsors" in sponsorship:
        reasons.append(
            "positive sponsorship indication"
        )

    elif "unclear" in sponsorship:
        reasons.append(
            "sponsorship requires verification"
        )

    elif "does not sponsor" in sponsorship:
        reasons.append(
            "future sponsorship may be a problem"
        )

    if not reasons:
        return (
            "Limited alignment with your current "
            "resume and target roles."
        )

    return "; ".join(reasons).capitalize() + "."




# ============================================================
# RESUME GAP / KEYWORD ANALYSIS
# ============================================================

JOB_SKILL_ALIASES = {
    "Python": ["python"], "SQL": ["sql"],
    "Excel": ["excel", "microsoft excel", "spreadsheets"],
    "PowerPoint": ["powerpoint", "presentations"],
    "Tableau": ["tableau"], "Power BI": ["power bi", "powerbi"],
    "R": ["r programming", "r language"],
    "Statistics": ["statistics", "statistical"],
    "Data Analytics": ["data analytics", "data analysis", "analytics"],
    "Financial Modeling": ["financial modeling", "financial modelling", "financial model"],
    "Valuation": ["valuation", "dcf", "discounted cash flow", "comparable companies"],
    "Machine Learning": ["machine learning"],
    "Capital IQ": ["capital iq", "s&p capital iq"],
    "Bloomberg": ["bloomberg"], "PitchBook": ["pitchbook"],
}

def analyze_resume_gaps(job, resume_data, matched_skills):
    """Transparent fallback analysis using only JD text and verified resume facts.

    Missing skills are JD-mentioned skills absent from the parsed resume. Suggested
    keywords are restricted to skills already present in the resume, so the system
    never recommends claiming an unsupported skill.
    """
    text = combined_job_text(job)
    resume_skills = set(resume_data.get("skills", []))
    jd_skills = []
    for skill, aliases in JOB_SKILL_ALIASES.items():
        if any(alias in text for alias in aliases):
            jd_skills.append(skill)
    missing = [skill for skill in jd_skills if skill not in resume_skills]

    clean_matched = [x.replace(" (related)", "") for x in matched_skills]
    suggested = list(dict.fromkeys([x for x in clean_matched if x in resume_skills]))

    gaps = []
    if missing:
        gaps.append("JD mentions skills not detected in resume: " + ", ".join(missing[:6]))
    years = re.findall(r"\b(\d+)\+?\s*(?:years|yrs)\b", text)
    if years and max(map(int, years)) >= 2:
        gaps.append(f"Posting mentions up to {max(map(int, years))} years of experience; verify fit against your actual experience.")
    if not gaps:
        gaps.append("No major resume gap was identified by the deterministic parser; review the full posting before applying.")
    return missing, gaps, suggested


# ============================================================
# SCORE ONE JOB
# ============================================================

def score_job(job, profile, resume_data):

    skills_score, matched_skills = score_resume_skills(
        job,
        resume_data
    )

    experience_score, matched_experience = (
        score_resume_experience(
            job,
            resume_data
        )
    )

    component_scores = {
        "job_function": score_job_function(
            job,
            profile
        ),

        "resume_skills": skills_score,

        "resume_experience": experience_score,

        "experience_level": score_experience_level(
            job
        ),

        "education": score_education(
            job,
            resume_data
        ),

        "sponsorship": score_sponsorship(
            job,
            profile
        ),

        "location": score_location(
            job,
            profile
        )
    }

    total_score = sum(component_scores.values())

    scored_job = job.copy()

    scored_job["match_score"] = total_score

    scored_job["match_category"] = (
        get_match_category(total_score)
    )

    scored_job["score_breakdown"] = component_scores

    scored_job["matched_resume_skills"] = (
        matched_skills
    )

    scored_job["matched_resume_experience"] = (
        matched_experience
    )

    scored_job["why_it_matches"] = build_match_reason(
        job, component_scores, matched_skills, matched_experience
    )

    fallback_missing, fallback_gaps, fallback_keywords = analyze_resume_gaps(
        job, resume_data, matched_skills
    )
    # Prefer conservative AI analysis when available; otherwise use the
    # transparent deterministic fallback. Never manufacture resume facts.
    scored_job["missing_skills"] = job.get("missing_skills") or fallback_missing
    scored_job["potential_gaps"] = job.get("potential_gaps") or fallback_gaps
    scored_job["suggested_resume_keywords"] = (
        job.get("suggested_resume_keywords") or fallback_keywords
    )

    return scored_job


# ============================================================
# SCORE ALL JOBS
# ============================================================

def score_jobs(jobs, profile, resume_data):

    scored_jobs = [
        score_job(job, profile, resume_data)
        for job in jobs
    ]

    scored_jobs.sort(
        key=lambda job: job["match_score"],
        reverse=True
    )

    return scored_jobs


# ============================================================
# DISPLAY RESULTS
# ============================================================

def display_ranked_jobs(jobs, limit=20):

    print()
    print("=== Ranked US Job Matches ===")
    print()

    if not jobs:
        print(
            "No matching US jobs were found "
            "after filtering."
        )
        return

    for index, job in enumerate(
        jobs[:limit],
        start=1
    ):

        scores = job["score_breakdown"]

        print(
            f"#{index} "
            f"{job.get('company', 'Unknown')} — "
            f"{job.get('title', 'Unknown')}"
        )

        print(
            f"Match Score: "
            f"{job['match_score']}/100"
        )

        print(
            f"Category: "
            f"{job['match_category']}"
        )

        print(
            f"Location: "
            f"{job.get('location', 'Unknown')}"
        )

        print(
            f"Sponsorship: "
            f"{job.get('sponsorship', 'Unknown')}"
        )

        print()

        print("Score Breakdown:")

        print(
            f"  Job Function:       "
            f"{scores['job_function']}/25"
        )

        print(
            f"  Resume Skills:      "
            f"{scores['resume_skills']}/20"
        )

        print(
            f"  Resume Experience:  "
            f"{scores['resume_experience']}/20"
        )

        print(
            f"  Experience Level:   "
            f"{scores['experience_level']}/15"
        )

        print(
            f"  Education:          "
            f"{scores['education']}/10"
        )

        print(
            f"  Sponsorship:        "
            f"{scores['sponsorship']}/5"
        )

        print(
            f"  Location:           "
            f"{scores['location']}/5"
        )

        print()

        skills = job.get(
            "matched_resume_skills",
            []
        )

        experience = job.get(
            "matched_resume_experience",
            []
        )

        print(
            "Matched Resume Skills: "
            + (
                ", ".join(skills)
                if skills
                else "None"
            )
        )

        print(
            "Matched Experience: "
            + (
                ", ".join(experience)
                if experience
                else "None"
            )
        )

        print()

        print(
            f"Why it matches: "
            f"{job['why_it_matches']}"
        )

        print(
            f"Apply: "
            f"{job.get('application_url', '')}"
        )

        print("-" * 75)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    from job_search import (
        load_profile,
        search_all_lever_companies
    )

    from job_filter import filter_jobs

    print()
    print("=== AI Job Search Agent ===")

    # --------------------------------------------------------
    # STEP 0 — RESUME
    # --------------------------------------------------------

    print()
    print("=== Step 0: Loading Resume ===")

    resume_data = parse_resume()

    if not resume_data.get("file_found"):
        print(
            "No resume found inside data/resume/."
        )
        raise SystemExit

    print(
        f"Resume loaded: "
        f"{resume_data.get('file_name')}"
    )

    print(
        f"Detected resume skills: "
        f"{len(resume_data.get('skills', []))}"
    )

    print(
        f"Detected experience areas: "
        f"{len(resume_data.get('experience_keywords', []))}"
    )

    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

    profile = load_profile()

    # --------------------------------------------------------
    # STEP 1 — SEARCH
    # --------------------------------------------------------

    print()
    print("=== Step 1: Searching Jobs ===")

    jobs = search_all_lever_companies(profile)

    print()
    print(
        f"Total jobs discovered: "
        f"{len(jobs)}"
    )

    # --------------------------------------------------------
    # STEP 2 — EXISTING FILTER
    # --------------------------------------------------------

    print()
    print("=== Step 2: Basic Filtering ===")

    filtered_jobs, removed_jobs = filter_jobs(
        jobs,
        profile
    )

    print(
        f"Jobs after basic filter: "
        f"{len(filtered_jobs)}"
    )

    # --------------------------------------------------------
    # STEP 3 — US ONLY
    # --------------------------------------------------------

    print()
    print("=== Step 3: US Location Filter ===")

    us_jobs, non_us_jobs = apply_us_location_filter(
        filtered_jobs
    )

    print(
        f"US jobs kept: "
        f"{len(us_jobs)}"
    )

    print(
        f"Non-US / ambiguous jobs removed: "
        f"{len(non_us_jobs)}"
    )

    # --------------------------------------------------------
    # STEP 4 — CAREER RELEVANCE
    # --------------------------------------------------------

    print()
    print("=== Step 4: Finance Career Filter ===")

    relevant_jobs, unrelated_jobs = apply_career_filter(
        us_jobs
    )

    print(
        f"Career-relevant jobs kept: "
        f"{len(relevant_jobs)}"
    )

    print(
        f"Unrelated jobs removed: "
        f"{len(unrelated_jobs)}"
    )

    # --------------------------------------------------------
    # STEP 5 — RESUME RANKING
    # --------------------------------------------------------

    print()
    print("=== Step 5: Resume-Based Ranking ===")

    ranked_jobs = score_jobs(
        relevant_jobs,
        profile,
        resume_data
    )

    display_ranked_jobs(
        ranked_jobs,
        limit=20
    )