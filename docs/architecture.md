# Architecture

Full design decisions for prates.fyi 2.0. If you're new to the project, read this once end-to-end, then refer back as needed. For day-to-day implementation, `CLAUDE.md` has the short version.

## 1. Context

### What this replaces

`prates.fyi v1` ran entirely inside a single Claude routine: research the news, generate HTML, upload to S3, invalidate CloudFront. One loop, one process, one responsibility-pile.

Three problems emerged:

- **Layout drift.** HTML structure varied day-to-day. Even small header changes were painful because there was no single template to edit. Some days the news page didn't render properly at all.
- **Duplicates.** Daily scraping pulled mostly the same articles for several consecutive days, because AI news doesn't actually break daily. The site felt repetitive.
- **No template/data separation.** Structural changes required editing the routine prompt and hoping the output stayed consistent across runs. It didn't.

### Design principles for v2

1. **Separate research (non-deterministic) from rendering (deterministic).** Claude does what only Claude can do (read the web, judge relevance, score articles). Code does what code does well (validate, template, deploy).
2. **JSON is the source of truth.** The entire site can be rebuilt from scratch from `data/articles.json`. Templates and styling are independent of content.
3. **Schema validation is the new "drift catcher."** Claude cannot drift the JSON structure because the build pipeline rejects malformed JSON.
4. **Git is the audit log.** Every article scrape lands as a commit. The repo IS the history. No separate logging or audit system.

## 2. System overview

```
       ┌─────────────────┐
       │  Claude Routine │   (weekday mornings)
       │   - scrape      │
       │   - dedup       │
       │   - score       │
       └────────┬────────┘
                │ commit + push (via fine-grained PAT)
                ▼
       ┌─────────────────┐
       │  GitHub repo    │   ai-daily-news (public)
       │  - JSON data    │
       │  - templates    │
       │  - renderer     │
       └────────┬────────┘
                │ push to main triggers
                ▼
       ┌─────────────────┐
       │ GitHub Actions  │
       │  - validate     │
       │  - render       │
       │  - deploy       │   (assumes IAM role via OIDC)
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ AWS S3 + CF     │
       └────────┬────────┘
                │
                ▼
          prates.fyi
```

## 3. Data model

### Article

The unit of content. One JSON object per article.

```json
{
  "id": "a1b2c3d4e5f6g7h8",
  "title": "Anthropic announces Claude Opus 4.7",
  "vendor": "Anthropic",
  "source": "anthropic.com",
  "url": "https://www.anthropic.com/news/claude-opus-4-7",
  "date": "2026-05-20",
  "description": "Anthropic released Claude Opus 4.7, the next iteration of its frontier model...",
  "score": 9,
  "scraped_at": "2026-05-20T06:14:33Z"
}
```

Fields:

- `id`: `sha256(url)[:16]`. Stable identifier, computed by Claude routine. Used for dedup.
- `title`: Article headline as published.
- `vendor`: The organization the news is *about* (e.g., "OpenAI", "Anthropic", "Google DeepMind"). Used for filtering/grouping.
- `source`: The publisher domain (e.g., "techcrunch.com", "arstechnica.com"). Distinct from `vendor`.
- `url`: Canonical URL of the article.
- `date`: Publication date (`YYYY-MM-DD`).
- `description`: 2–3 sentences, written by Claude.
- `score`: 0–10 integer. Higher = more important/interesting. See scoring below.
- `scraped_at`: ISO-8601 UTC timestamp of when Claude added it to the dataset.

### Scoring rubric (for Claude routine to follow)

Articles are scored 0–10 at scrape time. The rubric (refine over time):

- **9–10:** Major announcement from a frontier lab (new model release, significant capability), or research result that moves the field meaningfully.
- **7–8:** Notable product launches, important policy/regulatory news, significant funding/acquisition, well-reported analysis of an active topic.
- **5–6:** Solid news, but incremental. Feature updates, smaller funding rounds, interesting but niche research.
- **3–4:** Background coverage, opinion pieces, less novel takes on known topics.
- **0–2:** Filler. Generally not included unless it's a slow day.

The homepage "Today" section shows articles scoring ≥ 7 from the current day. "This Week" shows top 10 of last 7 days by score (regardless of threshold).

### Master file: `data/articles.json`

```json
{
  "version": 1,
  "updated_at": "2026-05-20T06:15:00Z",
  "articles": [
    { /* article object */ },
    { /* article object */ }
  ]
}
```

Articles are stored in a flat list, ordered however (renderer sorts at build time). The routine appends; it does not modify existing entries. Dedup is enforced by checking `id` before append.

The file is expected to grow unboundedly but slowly (~10 articles/day × small JSON each ≈ ~2 MB/year). Not a concern for git.

### Weekly summary: `data/summaries/YYYY-WNN.md`

ISO week numbering. One file per completed week. Markdown body with optional frontmatter:

```markdown
---
week: 2026-W21
period: 2026-05-18 to 2026-05-22
generated_at: 2026-05-22T07:00:00Z
---

# This week in AI

[Claude-written editorial summary of the week's themes and standout articles.]
```

Renderer embeds the summary at the top of the weekly archive page when the file exists.

## 4. Components

### 4.1 Claude routine

**Schedule:** Mon–Fri morning (e.g., 6am BRT).

**Responsibilities:**
1. Scrape configured AI news sources
2. For each candidate article: extract title, url, date, description; assign vendor + source; score 0–10
3. Compute `id = sha256(url)[:16]`
4. Pull the latest `data/articles.json` from the repo
5. Append new articles (skip if `id` exists)
6. Bump `updated_at`
7. Commit and push to `main` using fine-grained PAT

**Out of scope (intentionally):**
- HTML generation
- S3 / CloudFront operations
- Template knowledge of any kind

A second routine runs Friday morning (or Monday — TBD) to generate the previous week's summary file.

### 4.2 The repo

Public GitHub repo. Contains:
- Templates (`templates/`) — Jinja2
- Renderer (`scripts/build.py`) — single Python script
- Validator (`scripts/validate.py`)
- Static assets (`static/`)
- Data (`data/`)
- Schemas (`schemas/`)
- Workflows (`.github/workflows/`)
- Docs (`docs/`)

### 4.3 GitHub Actions

**`validate.yml`** — runs on every push and PR. Validates `data/articles.json` against `schemas/article.schema.json`. Validates summaries against `schemas/summary.schema.json` (if applicable). Fast, low cost, blocks broken data from landing on main.

**`deploy.yml`** — runs on push to `main` (after validate passes). Steps:
1. Checkout code
2. Set up Python + install deps
3. Re-run validate (defense in depth)
4. Render templates → `./build/`
5. Configure AWS credentials via OIDC (assume `PratesFyiDeployRole`)
6. `aws s3 sync ./build/ s3://prates-fyi-bucket --delete`
7. `aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"`

### 4.4 AWS

- **S3 bucket** `prates-fyi-bucket`: private, served only via CloudFront (OAC).
- **CloudFront distribution** at `prates.fyi`. Default behavior caches HTML for short TTL (e.g., 5 min) to reduce invalidation needs; static assets cached aggressively with versioned filenames.
- **IAM role** `PratesFyiDeployRole`: assumed via OIDC federation. Trust policy locked to this repo's `main` branch. Permissions policy scoped to one bucket + one distribution..

## 5. Pipeline flows

### 5.1 Daily flow (Mon–Fri)

1. Claude routine fires (e.g., 6am BRT)
2. Routine scrapes sources, scores new articles, writes commit to `main`
3. `validate.yml` runs → passes
4. `deploy.yml` runs:
   - Renders `index.html` with Today + This Week sections (filtered/sorted from `articles.json`)
   - Renders `archive/YYYY/MM/DD/` for the new day
   - Re-renders `weekly/YYYY-WNN/` for the current week (it shifts daily as new articles arrive)
   - Syncs to S3, invalidates CloudFront

### 5.2 Weekly summary flow

Friday (or following Monday) routine:
1. Reads `data/articles.json`
2. Filters to articles from the week being summarized
3. Sends them to Claude with a "write a weekly editorial summary" prompt
4. Writes `data/summaries/YYYY-WNN.md`
5. Commits and pushes
6. On next deploy, the weekly page picks up the summary file

### 5.3 Page generation logic

Given `data/articles.json` as input, the renderer produces:

| Page | Filter | Sort |
| --- | --- | --- |
| `index.html` (Today section) | `date == today` AND `score >= 7` | by score desc |
| `index.html` (This Week section) | `date >= today - 7d`, top 10 | by score desc |
| `archive/YYYY/MM/DD/index.html` | `date == YYYY-MM-DD` | by score desc |
| `weekly/YYYY-WNN/index.html` | `date in week WNN`, top 15 | by score desc, with summary if exists |
| `archive/index.html` | All days with articles | reverse chrono index |
| `weekly/index.html` | All completed weeks | reverse chrono index |

Empty days are allowed: `archive/YYYY/MM/DD/index.html` still renders with a "no articles this day" message rather than failing.

## 6. Decisions and rationale (ADRs)

### ADR-001: JSON in git, not in S3

Articles are small structured content (~500 bytes each). At ~10/day that's <2 MB/year. Git gives us free version control, diffability of every scrape, and the ability to rebuild the site from any point in history with no extra infrastructure. S3 storage was considered but adds an extra round-trip in the build pipeline and no benefit at this scale.

### ADR-002: GitHub Actions, not Lambda

GH Actions free tier (2000 min/month private, unlimited public) easily covers daily builds (~1–2 min each). The renderer lives next to the templates in the repo, which is where iteration happens. Lambda would add infrastructure to manage with no upside for this volume.

### ADR-003: OIDC federation, not access keys

Long-lived AWS access keys in a public (or even private) repo are unacceptable. OIDC issues short-lived (~1 hour) credentials per workflow run, gated by an IAM trust policy that locks assumption to this specific repo + main branch. Forks, feature branches, and arbitrary PRs cannot assume the role. No secrets to rotate, no leakage risk.

### ADR-004: Branch protection with admin bypass (Pattern 1)

`main` has standard branch protection: require PR for external contributions, no force pushes. The maintainer (and the Claude routine acting as the maintainer via fine-grained PAT) is on the bypass list and pushes JSON commits directly. Rationale: the risks branch protection mitigates (unreviewed contributions, accidental history rewrites) don't apply to the sole maintainer's own automation, and the ceremony of PR-per-scrape isn't justified for a personal project. Schema validation in CI is what actually catches bad data, not the PR review.

### ADR-005: Public repo

Two reasons. First, public repos get unlimited free Actions minutes, removing any quota worry. Second, the history of AI news scrapes (with scoring) is itself an interesting public artifact — a daily record of what the field looked like, judged by an AI. The repo is, in effect, the museum.

### ADR-006: Python + Jinja2 for the renderer

The maintainer's strongest stack. Stdlib + Jinja2 + jsonschema is a 3-line `requirements.txt`. No bundler, no Node ecosystem churn, no framework upgrades. If the project outgrows this, swap to 11ty/Astro — the JSON contract stays stable, so only the renderer and templates change.

### ADR-007: One master JSON file, not dated files

Considered `data/YYYY-MM-DD.json` per day. Rejected because: it makes dedup across days harder (you have to load multiple files), it complicates the weekly rendering (load 7 files), and it provides no real benefit since git already gives you per-commit history. One flat `articles.json` with a sortable `date` field is simpler.

### ADR-008: Score at scrape time, comparative re-rank weekly

Per-article scoring at scrape time is cheap and "good enough" for the daily view. The weekly summary involves a second Claude pass that sees the whole week's articles together — that pass can effectively re-rank by writing the narrative around the genuinely standout pieces. This gives editorial quality without paying for comparative ranking every day.

## 7. Future considerations (not v2 scope)

- RSS feed generation (trivial from JSON)
- Tag/topic system (add a `tags: []` field to articles, render tag pages)
- A "this month in AI" alongside weekly
- Email digest (subscribe to weekly summary)
- Re-running the renderer against historical data to backfill the archive with the new template (this is already supported by the design; just `python scripts/build.py` and deploy)
