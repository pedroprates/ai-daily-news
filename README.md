<p align="center">
  <img src="imgs/logo.png" alt="AI Daily News logo" width="120" />
</p>

<h1 align="center">AI Daily News</h1>

<p align="center">
  A daily digest of what matters in AI — researched by Claude, published automatically to <a href="https://prates.fyi">prates.fyi</a>.
</p>

<p align="center">
  <a href="https://github.com/pedroprates/ai-daily-news/actions/workflows/validate.yml"><img src="https://github.com/pedroprates/ai-daily-news/actions/workflows/validate.yml/badge.svg" alt="Validate" /></a>
  <a href="https://github.com/pedroprates/ai-daily-news/actions/workflows/deploy.yml"><img src="https://github.com/pedroprates/ai-daily-news/actions/workflows/deploy.yml/badge.svg" alt="Deploy" /></a>
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" />
</p>

---

## What is this?

**AI Daily News** is a fully automated static news site. Every weekday morning a Claude routine scrapes AI news sources, scores each article 0–10 by relevance, and commits a staging JSON file to this repo. GitHub Actions then validates, ingests, and renders the site — no human in the loop.

The repo is also the archive. Every scrape is a git commit, so the full history of what the AI field looked like, day by day, is permanently auditable.

---

## How it works

```
Claude Routine (daily)          Claude Routine (weekly)
  scrape + score news             summarize the week
        │                               │
        └──── commit + push (PAT) ──────┘
                       │
              GitHub: ai-daily-news
                       │
              ┌────────┼─────────────────┐
              ▼        ▼                 ▼
         validate   ingest.yml       deploy.yml
          .yml      dedup + merge    render HTML
         (schema)   → articles.json  S3 sync + CF
                                          │
                                     prates.fyi
```

### Pipeline stages

| Stage | Workflow | Trigger | What it does |
|---|---|---|---|
| **Validate** | `validate.yml` | Every push / PR | Schema-checks all JSON against `schemas/` |
| **Ingest** | `ingest.yml` | Push to `data/staging/**` | Deduplicates and merges staging files into `data/articles.json` |
| **Deploy** | `deploy.yml` | Push to `data/articles.json` | Renders Jinja2 templates → HTML, syncs to S3, invalidates CloudFront |

AWS credentials are never stored as secrets — the deploy workflow assumes `PratesFyiDeployRole` via OIDC federation, scoped to this repo's `main` branch.

---

## Project structure

```
.
├── data/
│   ├── articles.json          # Master article list — source of truth
│   ├── staging/               # Daily scrape output (YYYY-MM-DD.json per run)
│   └── summaries/             # Weekly editorial summaries (YYYY-WNN.md)
├── prompt/
│   ├── daily.md               # Claude routine prompt: research → staging JSON
│   └── weekly.md              # Claude routine prompt: summarise week
├── schemas/
│   ├── article.schema.json    # JSON Schema for articles.json
│   └── staging.schema.json    # JSON Schema for staging files
├── scripts/
│   ├── build.py               # Entry point: validate + render
│   ├── ingest.py              # Dedup + merge staging → articles.json
│   ├── render.py              # Jinja2 renderer
│   └── validate.py            # Schema validation
├── templates/                 # Jinja2 HTML templates
├── static/                    # CSS and static assets
├── .github/workflows/         # CI/CD pipelines
└── docs/                      # Architecture and setup docs
```

---

## Local development

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
git clone https://github.com/pedroprates/ai-daily-news.git
cd ai-daily-news
pip install -r requirements.txt
```

### Common commands

```bash
# Validate data/articles.json against the schema
python scripts/validate.py

# Render templates → ./build/
python scripts/build.py

# Preview the site locally
python -m http.server 8000 -d build
# Open http://localhost:8000

# Run tests
pip install -r requirements-dev.txt
pytest
```

The renderer is fully idempotent — same `articles.json` in, same HTML out. You can safely run `build.py` as many times as you like.

---

## Data model

Each article is a JSON object:

```json
{
  "id": "a1b2c3d4e5f6g7h8",
  "title": "Anthropic announces Claude Opus 4.7",
  "vendor": "Anthropic",
  "source": "anthropic.com",
  "url": "https://www.anthropic.com/news/claude-opus-4-7",
  "date": "2026-05-20",
  "description": "2–3 sentence summary written by Claude.",
  "score": 9,
  "scraped_at": "2026-05-20T06:14:33Z"
}
```

- `id` is `sha256(url)[:16]` — stable, used for deduplication.
- `score` (0–10): 9–10 = major model release or landmark research; 7–8 = notable launch or policy news; 5–6 = solid but incremental; below 5 = background/filler.
- The homepage shows articles scoring ≥ 7 from today, plus the top 10 of the last 7 days.

---

## Contributing

External contributions are welcome for anything except the raw article data (that's the Claude routine's job).

**Good contributions:**
- Bug fixes in `scripts/`
- Template / CSS improvements in `templates/` and `static/`
- Schema additions (add a field → update `schemas/` + renderer)
- Documentation improvements

**How to contribute:**

1. Fork the repo and create a branch from `main`.
2. Make your changes. If you touch `scripts/` or `schemas/`, run `pytest` and `python scripts/validate.py` before opening a PR.
3. Open a pull request — describe what changed and why.

> **Note:** The maintainer pushes JSON data commits directly to `main` via a fine-grained PAT. Branch protection is in place for all external contributors.

---

## Architecture & setup docs

- [`docs/architecture.md`](docs/architecture.md) — full design rationale, ADRs, and pipeline details
- [`docs/setup.md`](docs/setup.md) — first-time AWS + GitHub setup guide

---

## License

This project is licensed under the [MIT License](LICENSE).
