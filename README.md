# Internship Agent

Scrapes internship listings from Prosple and JobStreet, scores them against your resume and preferences using an LLM, and writes a ranked Markdown report to `output/report.md`.

## Limitations

- **CS/IT roles only** — listings for non-CS/IT fields (nursing, law, accounting, etc.) are automatically filtered out. Listings open to all courses are kept.
- **Two sources** — Prosple and JobStreet only for now.
- **Philippines-focused** — scoring weights Cebu-based and remote roles higher.

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

`.docx` is also supported (`data/resume.docx`). The agent uses the LLM to extract your skills, year level, degree, and experience summary from it. A cached version is saved to `data/profile.json` — it's re-parsed only if the resume file is newer than the cache.

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
