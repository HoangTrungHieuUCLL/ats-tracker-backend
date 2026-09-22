# ATS Keyword Tracker — Backend

FastAPI backend for a personal job-search tool: fetches job postings,
extracts ATS keywords via the Gemini API, and tracks application status.

- Background worker (asyncio task in the FastAPI lifespan) polls for queued
  jobs, fetches the posting, runs the extraction ladder (JSON-LD → known ATS
  APIs → trafilatura fallback), then analyzes the text with Gemini.
- Full API: job intake/listing/detail/editing, notes, retry/reanalyze,
  keyword dashboard + merge/rename, CSV export. See `/docs` for the live
  OpenAPI schema once the server is running.

## Local setup

1. Copy `.env.example` to `.env` and fill in `APP_PASSWORD`, `JWT_SECRET`,
   and `GEMINI_API_KEY` (get a free-tier key at
   https://aistudio.google.com/apikey). Leave `DATABASE_URL` as-is if you
   use the bundled Postgres.
2. Start Postgres:
   ```bash
   docker compose up -d
   ```
3. Install dependencies:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
4. Run migrations:
   ```bash
   alembic upgrade head
   ```
5. Start the API:
   ```bash
   uvicorn app.main:app --reload
   ```

API docs at http://localhost:8000/docs.

## Running tests

Tests run against a real Postgres database (never mocked) — create a
dedicated test database once:

```bash
docker compose exec db psql -U ats -d postgres -c "CREATE DATABASE ats_tracker_test OWNER ats;"
DATABASE_URL="postgresql://ats:ats@localhost:5432/ats_tracker_test" alembic upgrade head
```

Then:

```bash
pytest
```

Tests never make real network or LLM calls — httpx is mocked with `respx`,
and the Gemini client is monkeypatched where it's exercised.

To manually test extraction + analysis against the **real** Gemini API for
one posting:

```bash
python -m app.scripts.try_extract path/to/posting.txt
```

## Linting

```bash
ruff check .
```

## Railway deployment

1. Create a Railway project.
2. Deploy the Postgres template into it (Railway → New → Database →
   PostgreSQL). Its `DATABASE_URL` variable is what the backend service
   references below.
3. Create a service from this GitHub repo (connect the repo; Railway
   detects the `Dockerfile` automatically).
4. Set these service variables (Variables tab):
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (reference the Postgres
     service by its name in your project)
   - `GEMINI_API_KEY` — your free-tier key
   - `LLM_MODEL` — check https://ai.google.dev/gemini-api/docs/models for
     the current Gemini Flash-Lite model id
   - `APP_PASSWORD`, `JWT_SECRET` (`openssl rand -hex 32`)
   - `CORS_ORIGINS` — the frontend service's Railway domain, once generated
     (step 6)
   - `FETCH_MIN_SECONDS_PER_DOMAIN` (default `3`),
     `LLM_MIN_SECONDS_BETWEEN_CALLS` (default `6`), `LOG_LEVEL` (`INFO`)
5. Settings → Healthcheck Path: `/health`.
6. Settings → Networking → Generate Domain to get a public
   `*.up.railway.app` URL. This is the backend URL the frontend's
   `VITE_API_BASE_URL` must point to.
7. After the frontend's domain exists (see its README), come back and set
   `CORS_ORIGINS` to that domain.

The Dockerfile runs `alembic upgrade head` before starting uvicorn, so
migrations apply automatically on every deploy.
