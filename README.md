# Revision Battle

A gamified GCSE / A-level revision web app. Students revise with quick quizzes and bot battles, earn XP for a cosmetic avatar, and compete on leaderboards split by year group.

The full design (schema, API routes, phases, privacy rules) is in [`docs/PLAN.md`](docs/PLAN.md).

**Status:** Phases 1–4 are done. Students can make an account, browse 24 GCSE subjects, play 10-question quick quizzes (multiple choice, fill-the-blank, put-in-order, match-up) with an explanation after every answer, get wrong answers back on a 1 → 3 → 7 → 14-day spaced-repetition schedule, see their weak spots, and track exam countdowns. Battles, XP/avatars/leagues and the AI set creator are next (Phases 5–7).

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
uv run python -m app.cli seed
```

That loads all the subjects and topics plus 75 hand-checked demo questions. It's safe to re-run.

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

Step-by-step guide: [`docs/DEPLOY.md`](docs/DEPLOY.md). It covers Neon, then Render, then Cloudflare, and ends with a smoke test that checks the live site end to end.

## Accounts and privacy (Phase 2)

- **Sign up:** username, password and year group (dropdown, Years 7–13). Nothing else is collected.
- **Recovery code:** shown once at signup. It's the only way to reset a forgotten password, because there's no email.
- **Sessions:** server-side, in an httpOnly cookie (`__Host-` and Secure in prod), lasting 30 days from last use.
- **Rate limits:**
  - Logins: strict per username (10 failures per 15 min), loose per IP (100 per 15 min), so one school's shared Wi-Fi can't lock everyone out.
  - Signups: 30 per hour per IP.
  - Recovery: 5 attempts per hour per username.
  - IPs are only ever stored as HMACs.
- **Usernames:** filtered for profanity (including leetspeak) and for staff-impersonating names like `admin` or `teacher`. The word lists are in `backend/app/security/data/`.
- **Year groups:** stored as a cohort, so everyone moves up at 00:00 UK time on 1 September. Students can correct theirs once per school year.

## Content

**Topics.** `backend/seed/gcse_topics.json` is the school's GCSE subject/topic tree. `backend/seed/mfl_topics.json` adds French and German, cloned from Spanish as the file asked.
- Spec references, some exam boards and the French/German grammar lists are flagged in the files as needing a check against the official specs.
- Combined Science reuses the separate sciences' topics, so one question bank serves both.
- Questions tagged triple-only are hidden when playing through Combined Science.
- A Foundation/Higher toggle on each topic hides higher-only questions.

**Demo questions.** `backend/seed/questions/` holds 75 hand-checked questions: 25 each for Cell biology (AQA), Atomic structure (AQA) and Weimar & Nazi Germany (Edexcel). They cover all four question types.
- Every question passes the same automatic checks AI questions will face in Phase 7: unique options, exactly one blank, no "all of the above", and so on.
- Each topic's "learn more" link currently points to Wikipedia. BBC Bitesize blocks automated access, so swap in your preferred pages with the admin API.

**Admin.** Sign up in the app as normal, then promote yourself:

```bash
cd backend && uv run python -m app.cli make-admin YOUR_USERNAME
```

On Render's free plan there's no server shell. Run that command from your own computer with `DATABASE_URL` set to the Neon connection string.

Admins can use these endpoints (an admin screen comes with the reports queue in Phase 7):
- `POST /api/admin/topics/import`: same format as the seed files
- `PATCH /api/admin/topics/{id}`: rename, hide, or set the learn-more link
- `GET`/`POST`/`DELETE /api/admin/questions`: official questions. Answered questions are archived, never deleted, so stats stay right.

## How revision works (Phases 3–4)

- **Quick quiz:** 10 questions from a topic. The picker goes in this order: questions due for review first, then ones you haven't seen, then ones you recently got wrong, then everything else.
- **Marking:** fill-the-blank answers must match exactly once case, spacing and punctuation are ignored. There's no typo-tolerance on purpose ("meiosis" ≠ "mitosis"). Answers are never sent to the phone before you answer.
- **Spaced repetition (Leitner boxes):**
  - A wrong answer comes back after 1 day.
  - Getting it right on each review pushes it out to 3, then 7, then 14, then 30 days.
  - Something you get right the first time gets a single check-in after 2 weeks.
  - Getting a question right before it's due doesn't fast-track it.
- **Weak spots:** your accuracy per topic over the last 60 days, worst first. A topic needs at least 5 answers to be ranked.
