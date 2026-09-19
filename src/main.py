from job_search import (
    load_profile,
    search_all_lever_companies
)

from job_filter import (
    filter_jobs
)

from job_matcher import (
    apply_us_location_filter,
    apply_career_filter,
    score_jobs,
    display_ranked_jobs
)

from resume_parser import (
    parse_resume
)

from ai_analyzer import analyze_job

from database import (
    save_jobs,
    display_database_summary
)


def main():
    print()
    print("=" * 75)
    print("AI JOB SEARCH AGENT")
    print("=" * 75)

    # ========================================================
    # STEP 0 — LOAD PROFILE
    # ========================================================

    print()
    print("=== Step 0: Loading Job Search Profile ===")
    print()

    profile = load_profile()

    print("Target Roles:")

    for role in profile.get(
        "target_roles",
        []
    ):
        print(f"- {role}")

    print()

    print(
        "Requires Future Sponsorship:",
        profile
        .get("candidate", {})
        .get(
            "requires_future_sponsorship",
            False
        )
    )

    minimum_match_score = (
        profile
        .get("search", {})
        .get(
            "minimum_match_score",
            70
        )
    )

    print(
        "Minimum Preferred Match Score:",
        minimum_match_score
    )

    # ========================================================
    # STEP 1 — LOAD RESUME
    # ========================================================

    print()
    print("=== Step 1: Loading Resume ===")
    print()

    resume_data = parse_resume()

    if not resume_data.get(
        "file_found"
    ):
        print(
            "ERROR: No resume was found."
        )

        print(
            "Place your PDF, DOCX, or TXT resume "
            "inside data/resume/."
        )

        return

    if resume_data.get(
        "error"
    ):
        print(
            "ERROR: Resume could not be parsed."
        )

        print(
            resume_data["error"]
        )

        return

    print(
        f"Resume loaded: "
        f"{resume_data.get('file_name')}"
    )

    print(
        f"Detected skills: "
        f"{len(resume_data.get('skills', []))}"
    )

    print(
        f"Detected experience areas: "
        f"{len(resume_data.get('experience_keywords', []))}"
    )

    # ========================================================
    # STEP 2 — SEARCH JOBS
    # ========================================================

    print()
    print("=== Step 2: Searching Jobs ===")
    print()

    jobs = search_all_lever_companies(
        profile
    )

    print(
        f"Total jobs discovered: "
        f"{len(jobs)}"
    )

    if not jobs:
        print()
        print(
            "No jobs were discovered from the "
            "configured sources."
        )

        return

    # ========================================================
    # STEP 3 — BASIC FILTER
    # ========================================================

    print()
    print("=== Step 3: Basic Job Filtering ===")
    print()

    filtered_jobs, removed_jobs = (
        filter_jobs(
            jobs,
            profile
        )
    )

    print(
        f"Jobs kept after basic filter: "
        f"{len(filtered_jobs)}"
    )

    print(
        f"Jobs removed: "
        f"{len(removed_jobs)}"
    )

    # ========================================================
    # STEP 4 — UNITED STATES FILTER
    # ========================================================

    print()
    print("=== Step 4: US Location Filter ===")
    print()

    us_jobs, non_us_jobs = (
        apply_us_location_filter(
            filtered_jobs
        )
    )

    print(
        f"US jobs kept: "
        f"{len(us_jobs)}"
    )

    print(
        f"Non-US or ambiguous jobs removed: "
        f"{len(non_us_jobs)}"
    )

    # ========================================================
    # STEP 5 — CAREER RELEVANCE
    # ========================================================

    print()
    print("=== Step 5: Finance Career Filter ===")
    print()

    relevant_jobs, unrelated_jobs = (
        apply_career_filter(
            us_jobs
        )
    )

    print(
        f"Career-relevant jobs kept: "
        f"{len(relevant_jobs)}"
    )

    print(
        f"Unrelated jobs removed: "
        f"{len(unrelated_jobs)}"
    )

    if not relevant_jobs:
        print()
        print(
            "No career-relevant jobs remain "
            "after filtering."
        )
        return

    # ========================================================
    # STEP 5B — AI SEMANTIC REVIEW OF AMBIGUOUS SPONSORSHIP
    # ========================================================

    print()
    print("=== Step 5B: AI Sponsorship Review ===")
    print()

    ai_enabled = bool(__import__("os").getenv("OPENAI_API_KEY"))
    ai_rejected = []
    ai_kept = []

    total_ai_jobs = len(relevant_jobs)

    for index, job in enumerate(relevant_jobs, start=1):
        if index == 1 or index % 10 == 0 or index == total_ai_jobs:
            print(
                f"AI sponsorship review: "
                f"{index}/{total_ai_jobs}"
            )

        # Deterministic explicit language always wins.
        # AI is used only for ambiguous sponsorship.
        if (
            job.get("sponsorship") == "Sponsorship Unclear"
            and ai_enabled
        ):
            try:
                analysis = analyze_job(
                    job,
                    resume_data,
                    profile
                )

                if analysis:
                    job["ai_analysis"] = analysis

                    job["sponsorship"] = analysis.get(
                        "sponsorship",
                        "Sponsorship Unclear"
                    )

                    job["experience_requirements"] = analysis.get(
                        "experience_requirement",
                        job.get(
                            "experience_requirements",
                            []
                        )
                    )

                    job["missing_skills"] = analysis.get(
                        "missing_skills",
                        []
                    )

                    job["potential_gaps"] = analysis.get(
                        "potential_gaps",
                        []
                    )

                    job["suggested_resume_keywords"] = analysis.get(
                        "suggested_resume_keywords",
                        []
                    )

            except Exception as error:
                # Fail open as Unclear.
                # Never invent a sponsorship conclusion.
                job["ai_analysis_error"] = str(error)

        if (
            profile.get(
                "candidate",
                {}
            ).get(
                "requires_future_sponsorship",
                False
            )
            and job.get("sponsorship")
            == "Likely Does Not Sponsor"
        ):
            job["filter_reason"] = (
                "Explicitly does not sponsor "
                "(AI semantic review)"
            )
            ai_rejected.append(job)

        else:
            ai_kept.append(job)

    relevant_jobs = ai_kept

    print(
        f"Jobs kept after sponsorship gate: "
        f"{len(relevant_jobs)}"
    )

    print(
        f"Explicit no-sponsor jobs rejected: "
        f"{len(ai_rejected)}"
    )

    if not ai_enabled:
        print(
            "OpenAI semantic review skipped: "
            "OPENAI_API_KEY is not configured."
        )

    if not relevant_jobs:
        print(
            "No jobs remain after sponsorship review."
        )
        return

    # ========================================================
    # STEP 6 — RESUME-BASED MATCHING
    # ========================================================

    print()
    print("=== Step 6: Resume-Based Matching ===")
    print()

    ranked_jobs = score_jobs(
        relevant_jobs,
        profile,
        resume_data
    )

    print(
        f"Jobs ranked: "
        f"{len(ranked_jobs)}"
    )

    # ========================================================
    # STEP 7 — SAVE TO SQLITE
    # ========================================================

    print()
    print("=== Step 7: Updating Job Tracker ===")
    print()

    new_count, updated_count = (
        save_jobs(
            ranked_jobs
        )
    )

    print(
        f"New jobs added: "
        f"{new_count}"
    )

    print(
        f"Existing jobs updated: "
        f"{updated_count}"
    )

    # ========================================================
    # STEP 8 — DISPLAY TOP MATCHES
    # ========================================================

    print()
    print("=== Step 8: Top Job Matches ===")

    display_ranked_jobs(
        ranked_jobs,
        limit=20
    )

    # ========================================================
    # STEP 9 — DATABASE SUMMARY
    # ========================================================

    display_database_summary()

    # ========================================================
    # FINISHED
    # ========================================================

    print()
    print("=" * 75)
    print("JOB SEARCH COMPLETE")
    print("=" * 75)

    print()

    if new_count > 0:

        print(
            f"{new_count} new job(s) were added "
            f"to your tracker."
        )

    else:

        print(
            "No new jobs were added. "
            "Previously discovered jobs were updated."
        )

    print()

    print(
        "Database:"
    )

    print(
        "data/jobs.db"
    )

    print()


if __name__ == "__main__":
    main()