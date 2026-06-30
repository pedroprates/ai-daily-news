# Add `health.prates.fyi` Content Line

## Summary

Add a second content line (`health.prates.fyi`) alongside the existing tech AI-news site (`prates.fyi`), sharing the S3 bucket `prates-fyi-news` under separate key prefixes (`tech/`, `health/`) and a second CloudFront distribution. The Python pipeline (`render`, `history`, `deploy`, `ingest`, `validate*`, `build`) and the four GitHub workflows are made content-line-aware via a `content_line` parameter rather than duplicated. Two new Claude routines drive health research.

## Investigation

Verified against the code (not just git log). Key findings that shape implementation scope:

- `deploy.py` — `DEFAULT_BUCKET = "prates-fyi-news"`, uploads `build/` flat to bucket root. Needs a `prefix` param. Note: CLAUDE.md incorrectly names the bucket `prates-fyi-bucket`; the code says `prates-fyi-news`.
- `history.py` — `list_s3_dates` filters on `len(key) == 15 and key.endswith(".html")` (bare `YYYY-MM-DD.html`). A `tech/` prefix makes keys 20 chars → silently returns zero dates. Needs a `prefix` param and prefix-relative length check.
- `constants.py` — tech-only `VENDOR_COLORS` / `VENDOR_CSS_KEY` / `VENDORS`. Health needs parallel dicts.
- **Vendor enum lives in TWO schemas**: `schemas/article.schema.json` AND `schemas/staging.schema.json`. Health needs both `article.health.schema.json` and `staging.health.schema.json`.
- `validate.py` `detect_schema` routes by path: `name == "articles.json"` → article schema; `parent.name == "staging"` → staging schema. Health files (`data/health/articles.json`, `data/health/staging/*.json`) match the same names/parents, so they **silently validate against tech schemas** and reject health vendors. Must become content-line aware.
- `validate_staging.py` hook glob matches `*/data/staging/*.json` — silently skips `data/health/staging/`.
- `render.py` — `render()` already accepts `articles_path` but NOT `content_line`. It reads weekly summaries from module-level `SUMMARIES_DIR`; health summaries live elsewhere, so `summaries_dir` must thread through `render()` → `render_weekly_week`.
- `build.py` calls `render(today, output_dir, weekly_only)` without `articles_path` — always renders tech.
- Four GitHub workflows (`validate.yml`, `ingest.yml`, `deploy.yml`, `deploy-weekly.yml`) each read a single CloudFront distribution ID var.

## UX Decisions (from PM)

1. **Shared templates, content-line-aware styling.** Same Jinja2 template structure for both sites; a `content_line` variable controls palette, site name, nav branding. No second template copy. Health palette = greens/teals vs. tech amber.
2. **Health vendor taxonomy in a separate enum** (not extending the tech enum). Initial set: `["FDA", "NIH", "Pharma", "HealthTech", "Academia", "Industry"]`. `Industry` is the catch-all.
3. **Data layout** — tech paths unchanged; health under `data/health/{staging/,articles.json,summaries/}`:
   ```
   data/
     staging/           ← tech staging (unchanged)
     articles.json      ← tech master (unchanged)
     summaries/         ← tech weekly summaries (unchanged)
     health/
       staging/         ← health staging
       articles.json    ← health master
       summaries/       ← health weekly summaries
   ```
4. **Parameterized workflows** (`workflow_call` + `content_line` input) over duplication. Thin per-line trigger wrappers.
5. **One-time `aws s3 mv --recursive`** of existing content to `tech/` prefix during cutover (manual, maintainer-run, AFTER prefixed deploys are validated).
6. **Health prompts** at `prompt/health/daily.md` and `prompt/health/weekly.md`. Tech prompts stay at current paths.

## Technical Decisions (SEM)

- **`content_line` is the single carrier.** Type: `str`, values `"tech" | "health"`, default `"tech"` everywhere so existing tech calls are unchanged. Pass through function args and `--content-line` CLI flags — no config class.
- **Derive all paths from `content_line` via one helper.** Add `scripts/paths.py` (or a `paths_for(content_line)` helper) returning `{staging_dir, articles_path, summaries_dir, s3_prefix, schema_article, schema_staging}`. Single source of truth; every script imports it. `ponytail: a dict-of-paths keyed by content_line is the ceiling; no plugin system.`
- **S3 prefix format:** non-empty prefix always ends in `/` (`tech/`, `health/`); default `""` is valid for pre-migration tech state. `upload_dir` does `key = f"{prefix}{rel}"`.
- **`history.py` length guard becomes prefix-relative:** paginate with `Prefix=prefix`, strip prefix from each key, then check `len(rest) == 15 and rest.endswith(".html")`.
- **Two new schemas, not one:** `schemas/article.health.schema.json` AND `schemas/staging.health.schema.json` — both copies of their tech counterparts with only the `vendor` enum swapped. Full copies over a `$ref` abstraction (schemas are ~50 lines; indirection not worth it).
- **`validate.py` detection:** route on path containing `health` segment first, then name/parent. Map `(content_line, kind)` → schema. Existing tech routing unchanged.
- **`validate_staging.py`:** widen glob to also match `*/data/health/staging/*.json`; pick health staging schema when path contains `/health/`. Both hook mode and standalone mode.
- **CSS contract:** `HEALTH_VENDOR_CSS_KEY` values in `constants.py` MUST equal CSS class suffixes (`bar-{key}`, `tag-{key}`) and custom-property names. Agree key strings before TASK-A2 and TASK-B8 start — they are the shared API between backend and frontend.
- **No new dependencies.** Everything is arg-threading + Jinja vars + JSON. `requirements.txt` unchanged.
- **Cutover is the one irreversible, ordered step.** Sequence: (1) deploy code live writing to `tech/`, (2) `aws s3 mv` root objects → `tech/`, (3) flip distribution origin path to `/tech`, (4) invalidate. Keep old root objects until verified, then delete.
- **Tests:** extend existing unit tests with prefix + content_line assertions; no new test framework.

## Questions & Answers

**Resolved by investigation (no maintainer input needed):**
- `deploy.py` prefix, `history.py` prefix + guard, `ingest`/`validate` parameterization, `render` summaries threading — all confirmed as code changes above.

**Require maintainer confirmation before the AWS group executes:**

### Q (to `aws-infra-engineer`): Does the existing ACM cert cover `*.prates.fyi` or only `prates.fyi`?
**A:** Requires maintainer check. If single-domain, a new cert (or SAN extension) is needed for `health.prates.fyi`. ACM cert must be in `us-east-1` for CloudFront.

### Q (to `aws-infra-engineer`): Does `PratesFyiDeployRole` grant `s3:ListBucket` (needed by `history.py`) and `cloudfront:CreateInvalidation` on both distribution ARNs?
**A:** Requires maintainer confirmation. Current policy is likely `s3:PutObject` only; `ListBucket` and dual-distribution invalidation must be explicitly granted.

### Q (to maintainer): Confirm or amend the initial health vendor enum: `["FDA", "NIH", "Pharma", "HealthTech", "Academia", "Industry"]`?
**A:** Pending maintainer sign-off before schemas and constants are finalized.

---

## Task Checklist

### Group A — foundations (parallel)
- [ ] Create `schemas/article.health.schema.json` AND `schemas/staging.health.schema.json` (copies of tech schemas, health `vendor` enum substituted). — `backend-engineer`
- [ ] Add `HEALTH_VENDOR_COLORS`, `HEALTH_VENDOR_CSS_KEY`, `HEALTH_VENDORS` to `constants.py` parallel to tech dicts. Agree CSS key strings with frontend before TASK-B8. — `backend-engineer`
- [ ] Add `scripts/paths.py` with `paths_for(content_line)` returning `{staging_dir, articles_path, summaries_dir, s3_prefix, schema_article, schema_staging}`. — `backend-engineer`
- [ ] Scaffold `data/health/` with empty `staging/`, `summaries/`, and seed `articles.json` (`{"version":1,"updated_at":"","articles":[]}`). — `backend-engineer`
- [ ] (Infra, code-independent) Confirm ACM cert coverage; request/issue cert for `health.prates.fyi` if not wildcard. — `aws-infra-engineer`
- [ ] Create new CloudFront distribution for `health.prates.fyi` (origin = `prates-fyi-news`, origin path `/health`; HTTPS only; default root object `index.html`; attach cert). — `aws-infra-engineer`
- [ ] Update `PratesFyiDeployRole` IAM policy: `s3:PutObject` under both prefixes, `s3:ListBucket`, `cloudfront:CreateInvalidation` on both distribution ARNs. — `aws-infra-engineer`
- [ ] Create DNS record: `health.prates.fyi` CNAME → new CloudFront domain. — `aws-infra-engineer`

### Group B — script + template changes (parallel, after Group A schemas/constants/paths)
- [ ] `deploy.py`: add `prefix` (default `""`) to `upload_dir`/`deploy` + `--prefix` CLI; `key = f"{prefix}{rel}"`. — `backend-engineer`
- [ ] `history.py`: add `prefix` to `list_s3_dates` (paginate with `Prefix=`, strip prefix before `==15`/`.html` guard); thread `content_line` into `build_history` and history render for branding. — `backend-engineer`
- [ ] `ingest.py`: add `--staging-dir`, `--output`, `--schema` args via `paths_for`. — `backend-engineer`
- [ ] `validate.py`: route `data/health/**` paths to health schemas; add `--content-line` flag; ensure existing tech routing unchanged. — `backend-engineer`
- [ ] `validate_staging.py`: widen hook glob to include `*/data/health/staging/*.json`; select health staging schema when path contains `/health/`; same fix in standalone mode. — `backend-engineer`
- [ ] `render.py`: add `content_line` + `summaries_dir` params to `render()`; thread to `render_weekly_week`; pass `content_line` to every `.render()` call; make `load_articles` select CSS-key dict by content_line. — `backend-engineer`
- [ ] `templates/base.html`: consume `content_line` for site name and nav branding. — `frontend-engineer`
- [ ] Add health CSS: custom properties + `bar-{key}`/`tag-{key}` rules for each `HEALTH_VENDOR_CSS_KEY` (greens/teals). Key strings MUST match Group A `constants.py`. — `frontend-engineer`
- [ ] `templates/index.html`, `templates/daily.html` (and `weekly.html` if it renders vendor badges): use health vendor badge CSS when `content_line == "health"`. — `frontend-engineer`
- [ ] Write `prompt/health/daily.md` — health research routine targeting `data/health/staging/`, using health vendor enum, health-focused sources. — `backend-engineer`
- [ ] Write `prompt/health/weekly.md` — health weekly summary routine reading from `data/health/articles.json`. — `backend-engineer`

### Group C — integration (after Group B scripts)
- [ ] `build.py`: add `--content-line` (default `tech`); use `paths_for` to thread `articles_path`, `summaries_dir`, `content_line` into `render`; `prefix` into `history` and `deploy`. — `backend-engineer`
- [ ] Refactor `ingest.yml` to `workflow_call` with `content_line` input; thin trigger wrappers for `data/staging/**` (tech) and `data/health/staging/**` (health). — `backend-engineer`
- [ ] Refactor `deploy.yml` to `workflow_call`; wrappers for `data/articles.json` and `data/health/articles.json`; per-line `CLOUDFRONT_*_DISTRIBUTION_ID`. — `backend-engineer`
- [ ] Refactor `deploy-weekly.yml` to `workflow_call`; wrappers for `data/summaries/**` and `data/health/summaries/**`. — `backend-engineer`
- [ ] Update `validate.yml` diff globs to include `data/health/articles.json` and `data/health/staging/*.json`; validate both lines. — `backend-engineer`
- [ ] Add `CLOUDFRONT_HEALTH_DISTRIBUTION_ID` GitHub Actions variable (value from Group A infra task); document in `docs/architecture.md`. Manual repo-settings step. — `backend-engineer`
- [ ] Extend unit tests: prefix deploy key, `history.py` guard, `validate.py` schema routing, `paths_for` correctness. No new framework. — `backend-engineer`

### Group D — cutover + docs (after Group C; D1 → D2 → D3 must be ordered)
- [ ] **D1** Verify prefixed tech deploy writes to `s3://prates-fyi-news/tech/` correctly (run `deploy.yml` with prefix, check S3). — `aws-infra-engineer`
- [ ] **D2** Run one-time `aws s3 mv s3://prates-fyi-news/ s3://prates-fyi-news/tech/ --recursive --exclude "tech/*" --exclude "health/*"`; keep originals until verified. — `aws-infra-engineer`
- [ ] **D3** Flip existing `prates.fyi` distribution origin path to `/tech`; invalidate `/*`; verify. Delete old root objects when confirmed. — `aws-infra-engineer`
- [ ] Update `CLAUDE.md`: correct bucket name (`prates-fyi-news`), both site URLs, both data layouts, both CloudFront distribution vars. — `backend-engineer`
- [ ] Update `docs/architecture.md` with multi-content-line model, `content_line` contract, S3 prefix layout, cutover procedure. — `backend-engineer`
