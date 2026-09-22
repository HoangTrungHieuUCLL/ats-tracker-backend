# ATS Keyword Tracker — Backend

FastAPI backend for a personal job-search tool: fetches job postings, extracts
ATS keywords via the Gemini API, and tracks application status.

## Local setup

1. Copy `.env.example` to `.env` and fill in `APP_PASSWORD` and `JWT_SECRET`
   (leave `DATABASE_URL` as-is if you use the bundled Postgres).
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

```bash
pytest
```

Tests never make real network or LLM calls (httpx is mocked with `respx`
where needed).

## Linting

```bash
ruff check .
```

## Railway deployment

See the repo-root deployment checklist (added in the final build phase) for
step-by-step Railway setup. In short:

1. Create a Railway project, add the Postgres plugin.
2. Deploy this repo as a service; set `DATABASE_URL` (from the Postgres
   plugin), `GEMINI_API_KEY`, `LLM_MODEL`, `APP_PASSWORD`, `JWT_SECRET`,
   `CORS_ORIGINS` (the frontend's Railway domain).
3. Healthcheck path: `/health`.
