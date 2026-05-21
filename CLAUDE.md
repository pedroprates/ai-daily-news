# AI Daily News (prates.fyi 2.0)

Static AI news site. Claude routine researches news → writes staging JSON → GitHub Actions ingests into master JSON, renders HTML from templates → deploys to S3 + CloudFront.

This file is read on every Claude Code session. Keep it short. Deep context lives in `docs/`.

## Architecture in one paragraph

JSON is the source of truth. The Claude routine's only job is to research AI news and write candidates to `data/staging/YYYY-MM-DD.json` — a flat array of articles, scored 0–10. It never touches `data/articles.json` directly. A two-stage GitHub Actions pipeline handles the rest: `ingest.yml` deduplicates and merges the staging file into `data/articles.json`; `deploy.yml` validates, renders HTML from `templates/`, syncs to S3, and invalidates CloudFront. Each workflow triggers on a different path, so there is no loop. The renderer is deterministic and idempotent: same JSON in → same HTML out.

Routine prompts live in `prompt/` and are version-controlled here. The Claude.ai Routines UI contains only a thin pointer: *"Read `prompt/daily.md` from this repository and execute it exactly."* Updating a prompt is a git commit, not a change to the Routine settings.

Full design rationale: `docs/architecture.md`.

## Project layout

```
.
├── CLAUDE.md                  # This file
├── README.md
├── data/
│   ├── articles.json          # Master article list (source of truth)
│   ├── staging/               # Raw daily scrape output (YYYY-MM-DD.json per run)
│   └── summaries/             # Weekly editorial summaries (YYYY-WNN.md)
├── prompt/
│   ├── daily.md               # Claude routine: research → data/staging/
│   └── weekly.md              # Claude routine: summarise week → data/summaries/
├── schemas/
│   ├── article.schema.json    # JSON Schema for articles.json (master file)
│   ├── staging.schema.json    # JSON Schema for staging/YYYY-MM-DD.json
│   └── summary.schema.json    # JSON Schema for summaries
├── templates/                 # Jinja2 templates
│   ├── base.html
│   ├── index.html             # Homepage: Today + This Week
│   ├── daily.html             # Permanent daily archive page
│   └── weekly.html            # Permanent weekly archive page
├── static/                    # CSS, fonts, images
├── scripts/
│   ├── build.py               # Render JSON → HTML
│   └── validate.py            # Schema validation (used in CI)
├── .github/
│   └── workflows/
│       ├── validate.yml       # Runs on every push/PR
│       ├── ingest.yml         # Triggers on data/staging/** → dedup + merge into articles.json (not yet built)
│       └── deploy.yml         # Triggers on data/articles.json → render + S3 + CloudFront
├── build/                     # Render output (gitignored)
└── docs/
    └── architecture.md
```

## Key conventions

- **Never hand-write HTML for articles.** All article HTML comes from templates rendered against JSON. If layout needs changing, edit the template.
- **Schema validation is mandatory.** Any change to article structure must update `schemas/article.schema.json` AND the renderer. The Action will block deploys for invalid JSON.
- **Renderer is idempotent.** The entire site can be rebuilt from `data/articles.json` at any time. No state lives outside JSON.
- **Article IDs are URL hashes.** `id = sha256(url)[:16]`. Used for dedup.
- **Branch protection on `main` with admin bypass.** The maintainer (and the Claude routine acting as the maintainer) pushes JSON commits directly to `main`. External contributions go through PRs.
- **No long-lived AWS credentials.** Deploys use OIDC federation to assume `PratesFyiDeployRole`.

## Stack choices (tentative — confirm or change in setup)

- **Renderer:** Python 3.11 + Jinja2. Single `scripts/build.py`. Simple, scriptable, fast for this size.
- **Schema validator:** `jsonschema` (Python).
- **CSS:** Plain CSS, custom tokens. No build step. Templates in Atomic Design pattern (atoms → molecules → organisms → pages).
- **Deps:** Keep `requirements.txt` minimal (jinja2, jsonschema, that's about it).

If you want to swap to 11ty/Astro/Hugo later, the only thing that needs to change is `scripts/build.py` and the templates. The JSON contract stays the same.

## Common commands

```bash
# Local dev
python scripts/validate.py                # Validate data/articles.json against schema
python scripts/build.py                   # Render templates → ./build/
python -m http.server 8000 -d build       # Preview at localhost:8000

# Deploy is automatic on push to main (see .github/workflows/deploy.yml)
```

## Critical context for Claude Code

- Site: `https://prates.fyi` (CloudFront → S3 bucket `prates-fyi-bucket`)
- AWS region: `us-east-1`
- IAM role for deploys: `PratesFyiDeployRole` (assumed via OIDC, no static keys)
- Solo maintainer, public repo — history of AI news scrapes is part of the artifact
- The previous version of this site lived entirely inside a Claude routine that did research + HTML + S3 upload. This v2 splits that into: routine (research → JSON only) + repo (JSON → HTML → deploy). See `docs/architecture.md` for the full why.

## What's intentionally NOT in scope

- Comments, user accounts, analytics dashboards — this is a static reader, nothing else
- Real-time updates — daily cadence is the whole point
- Multiple authors — solo maintainer
- A CMS — JSON files are the CMS
