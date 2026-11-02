# Revision Battle

A gamified GCSE / A-level revision web app. Students revise with quick quizzes and bot battles, earn XP for a cosmetic avatar, and compete on leaderboards split by year group.

The full design (schema, API routes, phases, privacy rules) is in [`docs/PLAN.md`](docs/PLAN.md).

**Status:** Phase 1 (scaffold) is done. The app shell, database schema, health check and Cloudflare proxy work; features land phase by phase.

## Stack

| Part | Tech | Hosted on |
|---|---|---|
| API | Python 3.13, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2 | Render |
| Database | Postgres 16 | Neon (Docker Compose locally) |
| Frontend | React, Vite, TypeScript, Tailwind, TanStack Query, React Router | Cloudflare Workers (static assets) |
| Proxy | Cloudflare Worker: forwards `/api/*` to Render so the session cookie is first-party | Cloudflare |
| AI | Anthropic API for drafting questions from notes (optional) | — |

## Repo layout

```
backend/    FastAPI app, models, Alembic migrations, tests, seed data
frontend/   React app + the Cloudflare Worker (worker/) and wrangler.jsonc
docs/       PLAN.md, the design doc
infra/      local Postgres init script
```

## Local setup

You need **Python 3.13 + [uv](https://docs.astral.sh/uv/)**, **Node 22**, and either **Docker** or a local **Postgres 16**.

### 1. Database

```bash
docker compose up -d db
```

That creates `revision_battle` (dev) and `revision_battle_test` (tests), user `rb` / password `rb`.

### 2. Backend (API on http://localhost:8000)

```bash
cd backend
```

```bash
cp .env.example .env
```

```bash
uv sync
```

```bash
uv run alembic upgrade head
```

```bash
uv run uvicorn --factory app.main:create_app --reload --port 8000
```

API docs are at http://localhost:8000/api/docs (dev only).

### 3. Frontend (app on http://localhost:5173)

In a second terminal:

```bash
cd frontend
```

```bash
npm install
```

```bash
npm run dev
```

Open http://localhost:5173 on your laptop. To test on a phone on the same Wi-Fi, run `npm run dev -- --host` and open the "Network" URL it prints. Vite forwards `/api` to the backend, so dev is same-origin just like prod. The home screen shows **Server online** when everything is wired up.

### Optional: run the real Cloudflare Worker locally

```bash
cd frontend
```

```bash
cp .dev.vars.example .dev.vars
```

```bash
npm run cf:dev
```

This builds the app and serves it at http://localhost:8787 through the actual Worker, including the `/api` proxy.

## Tests

```bash
cd backend && uv run pytest
```

```bash
cd backend && uv run ruff check . && uv run ruff format --check .
```

```bash
cd frontend && npm run typecheck && npm test
```

Backend tests need Postgres; they use `TEST_DATABASE_URL` (default `postgresql://rb:rb@localhost:5432/revision_battle_test`) and wipe that database's schema on each run. CI runs everything on every push (`.github/workflows/ci.yml`).

## Environment variables

**Backend:** see [`backend/.env.example`](backend/.env.example). The important ones:

| Var | Notes |
|---|---|
| `DATABASE_URL` | Neon's **pooled** connection string, pasted as-is (sslmode and PgBouncer quirks are handled in code) |
| `DATABASE_URL_DIRECT` | Neon's **direct** string, used for migrations (optional) |
| `SECRET_KEY` | Long random string, required in prod |
| `PROXY_SHARED_SECRET` | Must match the Worker's secret, required in prod |
| `FRONTEND_ORIGIN` | The site's https origin in prod |
| `ANTHROPIC_API_KEY` | Optional; only AI question drafting needs it |

**Worker:** `BACKEND_URL` is set in `frontend/wrangler.jsonc`. `PROXY_SHARED_SECRET` is a Wrangler secret. For local runs, both go in `frontend/.dev.vars`.

## Deploying

Full step-by-step deploy instructions arrive with the first real deploy in Phase 2. The shape is:

1. **Neon:** create a project in the London region (`aws-eu-west-2`) and copy the pooled and direct connection strings.
2. **Render:** create a Blueprint from `render.yaml` and fill in the secret env vars. Migrations run automatically on start. The free tier sleeps after ~15 min idle, so the first request after that takes up to a minute.
3. **Cloudflare:** set `BACKEND_URL` in `frontend/wrangler.jsonc` to your Render URL, then:

```bash
cd frontend && npx wrangler secret put PROXY_SHARED_SECRET
```

```bash
cd frontend && npm run cf:deploy
```

## Topic data

`backend/seed/gcse_topics.json` holds the school's GCSE subject/topic tree. Spec references and some exam boards are marked as needing a check against the official specs (see its `meta` and `notes` fields). Combined Science reuses the separate sciences' topics, so one question bank serves both; triple-only and higher-tier subtopics are tagged automatically on import.
