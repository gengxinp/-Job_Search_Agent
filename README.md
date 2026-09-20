# Agentic AI Job Search & Notification System — V2

A student-readable Python agent that searches legitimate public ATS feeds, filters and ranks jobs, compares them with a resume, persists an application tracker in SQLite, provides a Streamlit dashboard, and sends a weekly email of new opportunities.

## Workflow

`Search → Filter → Sponsorship verification → AI semantic review → Resume match → 0–100 score → Deduplicate → SQLite tracker → Dashboard → Weekly email`

Sources currently supported: Lever, Greenhouse, and Ashby public job boards. The search includes both early-career/new-grad roles and realistic professional-hiring analyst/associate roles. Senior titles and roles explicitly requiring 4+ years are rejected by default; thresholds are configurable in `config/profile.yaml`.

## Sponsorship policy

The candidate requires future employer sponsorship. Every job is classified as `Likely Sponsors`, `Sponsorship Unclear`, `Work Authorization / Export Control Risk`, or `Likely Does Not Sponsor`. `Likely Does Not Sponsor` is a hard rejection: it cannot enter ranking, the tracker as a new recommendation, or the weekly email. `Sponsorship Unclear` jobs remain eligible. `Work Authorization / Export Control Risk` jobs remain eligible but receive lower ranking priority. For unclear postings, the agent can re-check the real application page with a normal HTTP request; access failures remain `Unclear`. It never infers sponsorship from company size.

## Setup

1. Create a virtual environment and install dependencies: `pip install -r requirements.txt`.
2. Put one PDF, DOCX, or TXT resume in `data/resume/`.
3. Copy `.env.example` to `.env` and fill in your own secrets. Never commit `.env`.
4. Edit `config/profile.yaml` for roles, locations, thresholds, and notification email.

Environment variables:

- `OPENAI_API_KEY` — optional but recommended for semantic JD analysis.
- `OPENAI_MODEL` — defaults to `gpt-5.6-luna`.
- `EMAIL_SENDER`, `EMAIL_APP_PASSWORD`, `SMTP_SERVER`, `SMTP_PORT` — weekly email credentials.

The system still runs without an OpenAI key; ambiguous sponsorship remains `Unclear` instead of being guessed.

## Commands

Search, filter, rank, and update tracker:

```bash
python src/main.py
```

Open the Job Tracker dashboard:

```bash
streamlit run src/dashboard.py
```

Preview the weekly report without sending:

```bash
python src/email_notifier.py
```

Run the complete weekly search and send the email:

```bash
python run_weekly.py
```

Run tests:

```bash
pytest -q
```

## Dashboard / tracker

SQLite data is stored at `data/jobs.db`. The dashboard shows total jobs, new jobs this week, excellent/strong matches, `Likely Sponsors`, `Sponsorship Unclear`, `Export Control Risk`, applications, and interviews. It supports filters for title/company, location, job type, sponsorship, score, and application status. Statuses are: New, Interested, Applied, Interview, Offer, Rejected, Not Interested, and Closed. Existing application status is preserved on future searches.

## Weekly email

Subject: `Weekly AI Job Search Report`. Only recent, not-previously-emailed jobs meeting the configured minimum score are eligible. As a second safety gate, the email query itself excludes `Likely Does Not Sponsor`. Jobs are marked emailed only after SMTP reports a successful send.

## Automation

### macOS/Linux cron

From the project directory, run `pwd` and note the full path. Then `crontab -e` and add a weekly entry such as Monday 9:00 AM local time:

```cron
0 9 * * 1 cd /FULL/PATH/Job_Search_Agent && /FULL/PATH/TO/python run_weekly.py >> data/weekly.log 2>&1
```

Use the Python executable from your virtual environment (run `which python` while the environment is active). The laptop must be awake for cron to run.

### GitHub Actions

A starter workflow is included at `.github/workflows/weekly-job-search.yml`. Add the required values as GitHub repository Actions secrets. Do not commit `.env`. GitHub Actions can run while the laptop is off. Note that a SQLite database stored only on the ephemeral runner will not persist unless you deliberately add a persistence strategy; for reliable local application history, the Mac/desktop scheduled run is the simplest option.

## Security and access rules

Secrets are read from environment variables. `.env` is ignored by Git. The code does not print secret values. The agent uses legitimate public job endpoints/pages and does not bypass CAPTCHA, login requirements, robots/access controls, or rate limits. It never automatically applies to jobs; the user reviews each real application URL before applying.

## Project structure

```text
Job_Search_Agent/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── config/profile.yaml
├── data/resume/
├── src/
│   ├── main.py
│   ├── job_search.py
│   ├── job_filter.py
│   ├── job_matcher.py
│   ├── resume_parser.py
│   ├── ai_analyzer.py
│   ├── database.py
│   ├── email_notifier.py
│   └── dashboard.py
├── tests/
├── run_weekly.py
└── .github/workflows/weekly-job-search.yml
```

## Important limitations

Job availability and ATS content can change at any time. A posting may omit sponsorship language; those jobs are intentionally labeled `Sponsorship Unclear`. AI analysis is conservative and is not allowed to invent resume facts. The agent does not guarantee that every job on the internet is discovered; its coverage is the configured public ATS sources.
