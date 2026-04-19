# Internship Agent

## What is this?

I kept doing the same thing over and over: open a job board, scroll through listings, copy one into ChatGPT, ask "does this fit me?", repeat. It was tedious and I wanted both sides of that loop automated — the searching and the "is this actually relevant to me" judgment.

This project is also a hands-on way to build real experience with two things I hadn't done in a proper project yet: web scraping and AI agents. Less tutorial, more just building something I'd actually use.

The agent scrapes internship listings from Prosple and JobStreet, scores them against your resume and preferences using an LLM, and writes a ranked Markdown report to `output/report.md`.

## Limitations

- **CS/IT roles only** — listings for non-CS/IT fields (nursing, law, accounting, etc.) are automatically filtered out. Listings open to all courses are kept.
- **Two sources** — Prosple and JobStreet only for now.
- **Philippines-focused** — scoring weights Cebu-based and remote roles higher.
- **Scoring still needs work** — the LLM-based scoring isn't perfectly calibrated. Certain traits (like location or compensation) can end up weighted more heavily than they should be in practice, and the scores don't always reflect what actually makes a listing a good fit. Treat the ranking as a rough guide, not a final verdict.

---

## How it works

Three independent layers communicate through flat files:

1. **Scrapers** — Playwright-based scrapers fetch listings from Prosple and JobStreet and write raw JSON to `data/raw/`
2. **Agent** — A Groq-powered agentic loop reads the raw listings and calls tools in sequence: filter expired → fetch full descriptions → enrich fields with LLM extraction → score → deduplicate → rank → write report
3. **Output** — A ranked Markdown report saved to `output/report.md`

The LLM client is a thin swappable wrapper — switching from Groq to Anthropic is a two-line change.

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright browser

```bash
playwright install chromium
```

### 3. Get a Groq API key

1. Go to [console.groq.com](https://console.groq.com) and sign up for a free account.
2. Navigate to **API Keys** and create a new key.
3. Create a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

### 4. Add your resume

Place your resume in the `data/` folder. It must be named exactly:

```
data/resume.pdf
```

`.docx` is also supported (`data/resume.docx`). Parses your resume using an LLM to extract skills, year level, degree, and experience. A cached version is saved to `data/profile.json` — it's re-parsed only if the resume file is newer than the cache.

### 5. Configure your preferences

Edit `data/preferences.json` to set your target role and preferred location:

```json
{
    "target_role": "Software Engineer",
    "location_preference": "Cebu"
}
```

`target_role` is used when scoring role relevance. `location_preference` affects the location scoring — Cebu-based and remote roles score highest.

---

## Running

### Full run (scrape + rank + report)

```bash
python main.py
```

This scrapes fresh listings from Prosple and JobStreet, scores them, and writes the report.

### Skip scraping (use cached listings)

```bash
python main.py --skip-scrape
```

Skips the scraping step and uses whatever JSON files are already in `data/raw/`. Useful if scraping already ran and you just want to re-score or re-rank.

### Resume from a checkpoint

```bash
python main.py --resume
```

If a previous run was interrupted mid-pipeline, this picks up from the last completed stage instead of starting over. Checkpoints are saved in `data/checkpoints/`.

---

## Output

The ranked report is written to `output/report.md`. Each listing includes:

- Score out of 100 and a rationale
- Location, deadline, compensation
- Required skills and eligibility constraints
- A 1–2 sentence summary of what the intern will do
- A link to the original listing

## Sample Output

```
## #1 — Academy Program for Site Reliability Engineer @ OpsWerks
Score: 87/100
Why: The candidate's skills match the listing's requirements, with proficiency in Python and other
relevant technologies, and the role is relevant to their target role as a Software Engineer. The
candidate also meets the eligibility requirements, is a good location fit, and the internship is paid.
Location: Cebu Office, Cebu City, Philippines
Deadline: 2027-03-10
Compensation: competitive industry allowance with 1 day of paid sick leave per month and paid certification opportunities
Skills: C++, Python, BASH shell scripting
Eligibility: B.S. Computer Engineering graduate from a reputable school in Visayas or Mindanao, Less than 2 years of working experience

Learn and understand all the subjects included in the Academy Syllabus, complete and present all
assigned projects, tasks, and case studies, build healthy relationships among other interns.

[View listing →](https://ph.prosple.com/graduate-employers/opswerks/jobs-internships/academy-program-for-site-reliability-engineer-1)

---

## #2 — IT Intern @ Unknown
Score: 85/100
Why: The candidate's skills match the general IT intern requirements well, and the role is relevant
to their target role as a Software Engineer. The location in Cebu City also aligns with the
candidate's preference, and the internship is likely to be paid.
Location: Cebu City, Cebu
Deadline: Not specified
Compensation: Not specified
Eligibility: prior to graduation

[View listing →](https://ph.jobstreet.com/job/90261104)

---

## #3 — AI Engineer Intern @ Foundry for Good Philippines
Score: 82/100
Why: The candidate's skills in programming languages and experience in building scalable backend
systems partially align with the AI Engineer Intern role, and the paid stipend and remote work
arrangement are favorable.
Location: Not specified
Deadline: Not specified
Compensation: PHP 60,000 upon successful completion
Skills: LLMs like Anthropic/OpenAI, GitHub, APIs

Build AI agents to automate research tasks and ship production-level systems. Develop automated
workflows to replace human research tasks. Ship real systems used in production within 2-4 weeks.

[View listing →](https://ph.prosple.com/graduate-employers/foundry-for-good-philippines/jobs-internships/ai-engineer-intern)
```

---

## Running tests

```bash
pytest
```

To run a specific test file or test:

```bash
pytest tests/test_tools.py
pytest tests/test_tools.py::test_score_listing_cebu_scores_higher_than_manila
```
