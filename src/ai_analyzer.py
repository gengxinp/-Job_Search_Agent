"""Optional OpenAI-powered semantic analysis for ambiguous job postings.

The deterministic filters remain authoritative. AI is used only where it adds
value, and the system continues to work if OPENAI_API_KEY is not configured.
"""
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def _extract_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("AI response did not contain JSON")
    return json.loads(text[start:end + 1])


def analyze_job(job, resume_data=None, profile=None):
    """Return conservative semantic analysis of a job posting.

    Sponsorship values are restricted to the same three labels used elsewhere.
    An absent API key returns None rather than breaking the search workflow.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return None

    client = OpenAI(
    timeout=30.0,
    max_retries=1,
)
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

    resume_summary = {
        "education": (resume_data or {}).get("education", []),
        "skills": (resume_data or {}).get("skills", []),
        "experience_keywords": (resume_data or {}).get("experience_keywords", []),
    }

    prompt = f"""
You are a conservative job-posting classifier. Use ONLY the text provided.
The candidate requires future US employer visa sponsorship.

Return one JSON object with exactly these keys:
sponsorship, experience_requirement, professional_hiring_fit,
matched_skills, missing_skills, potential_gaps, suggested_resume_keywords, why_match.

Rules for sponsorship:
- "Likely Does Not Sponsor" if the posting explicitly says no sponsorship, cannot/will not sponsor,
  no current or future sponsorship, or requires permanent/unrestricted US work authorization.
- "Likely Sponsors" only when sponsorship is explicitly available/considered.
- Otherwise "Sponsorship Unclear". Never infer sponsorship from company size or reputation.

professional_hiring_fit must be true/false and should be true for relevant finance/data/analytics
professional roles that are plausibly accessible to an early-career candidate, even if not labeled new-grad.
Do not invent resume skills or experience. Suggested resume keywords must be concepts already supported
by the resume, merely phrased to align with the posting.

JOB:
Title: {job.get('title', '')}
Company: {job.get('company', '')}
Location: {job.get('location', '')}
Description: {str(job.get('description', ''))[:14000]}

RESUME FACTS:
{json.dumps(resume_summary, ensure_ascii=False)}
"""

    response = client.responses.create(
        model=model,
        input=prompt,
    )
    data = _extract_json(response.output_text)

    allowed = {
        "Likely Sponsors",
        "Sponsorship Unclear",
        "Likely Does Not Sponsor",
    }
    if data.get("sponsorship") not in allowed:
        data["sponsorship"] = "Sponsorship Unclear"
    return data
