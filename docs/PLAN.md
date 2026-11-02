# Revision Battle: Build Plan

**Status:** approved 2 Nov 2026 · Phase 1 (scaffold) done

**Decisions locked in:** Cloudflare Workers static assets (not Pages) · recovery codes · report threshold N = 3 · free `workers.dev` address for now · topic tree from the school's GCSE file (`backend/seed/gcse_topics.json`).

This doc is the source of truth for the build. Later phases refer back to it, and it gets updated whenever a decision changes.

---

## 0. TL;DR

- **Backend:** FastAPI + async SQLAlchemy 2.0 + Alembic on Render, talking to Neon Postgres.
- **Frontend:** React + Vite + TS, mobile-first. Hosted on Cloudflare with a small Worker that proxies `/api/*` to Render, so the browser treats the API as **same-origin**. That makes login cookies work on iPhones (see 1.1).
- **Auth:** server-side sessions in an httpOnly cookie. No JWTs.
- **Spaced repetition:** Leitner boxes with intervals of 1 / 3 / 7 / 14 / 30 days.
- **AI pipeline:** grounded generation, then code checks, then a separate AI verifier, then mandatory human approval (enforced in the DB), then reports.
- **Pure game logic** (year groups, SRS, scoring, bot, XP, streaks, leagues) lives in `backend/app/domain/` as DB-free functions, so it can be unit-tested hard.

---

## 1. Changes I'm proposing to the spec

### 1.1 Cross-site cookies will break login on iPhones, so the API goes same-origin
With the frontend on `*.pages.dev` / `*.workers.dev` and the backend on `*.onrender.com`, the two are different sites. A session cookie set by Render would be a **third-party cookie**. Safari blocks those by default, and on iPhones basically every browser runs on Safari's engine. Most users are on phones, so login would silently fail for a big share of them.

**Fix:** the frontend only ever calls `/api/...` on its own origin. A ~30-line Cloudflare Worker forwards those requests to Render. The cookie is then first-party (`SameSite=Lax`), and production needs no CORS preflights. The backend rejects any request without the Worker's shared-secret header (except `/api/health` and localhost in dev). That stops people bypassing the proxy or spoofing their IP for rate limits. CORS stays locked to the frontend origin as a second layer.

*Alternative:* buy a domain and use `app.yourdomain` + `api.yourdomain`, which are same-site, so cookies work. The Worker approach works without a domain.

### 1.2 Cloudflare Workers static assets instead of Pages
Cloudflare's own docs now say "Start new projects with Workers": Pages keeps working, but new features go to Workers. Static assets are free on both. We need a Worker for the proxy anyway, so one Worker serves the React build and proxies `/api/*`. If you'd rather stick with Pages, the same proxy runs as a Pages Function (a small change).

### 1.3 Password recovery codes
No email means no "forgot password", and teenagers forget passwords constantly. At signup the user gets a one-time **recovery code** (e.g. `QZ7K-M2PD-X9RT-4HWN`), stored only as a hash. Username + recovery code lets them set a new password, and they can regenerate the code in settings. It isn't personal data. Without it, a forgotten password means a lost account and a lost streak.

### 1.4 Tests and a first deploy early, not in Phase 8
Each phase ships with its own pytest coverage: year-group tests in Phase 2, SRS in 4, battles in 5, leagues in 6. Phase 8 fills the gaps and adds frontend tests. The **first deploy smoke test** happens at the end of Phase 2. The Neon/Render/Cloudflare wiring is what tends to break, so it gets proven early.

### 1.5 Rate limits that survive school Wi-Fi
A whole school often shares one public IP. Strict per-IP limits would lock out a class signing up together, so:
- **Login:** strict per username (10 failures per 15 min), loose per IP (100 per 15 min).
- **Signup:** 30 per hour per IP.
- **Recovery:** 5 per hour per username.
- **AI generation:** a per-user daily limit plus a global daily cap.
- **Join-code attempts:** 20 per hour per user.

IPs are only ever stored as HMAC hashes in a short-lived counter table.

### 1.6 Smaller defaults I picked
- **Fill-the-blank** is an exact match after normalising case, spacing, punctuation and quote/dash styles, checked against a list of accepted answers. There's **no fuzzy typo matching**, because "meiosis" is two edits from "mitosis". A per-question `case_sensitive` flag handles chemistry (Co ≠ CO).
- **Bosses only exist for official topics**, so nobody can farm cosmetics by making a 3-question set.
- **Anti-grind XP:** re-answering a question you already got right today gives 2 XP instead of 10. Grinding one easy quiz won't win a league, but covering new material will.
- **Leaderboards** show username, avatar and XP only, with no click-through to a profile. The signup screen says "don't use your real name" and offers random username suggestions (e.g. `CosmicOtter42`).
- **Quick quiz has no timer**, because it's for learning. Battles and bosses are timed.

---

## 2. Architecture

```
 Phone browser
     │  https://revisionbattle.<you>.workers.dev
     ▼
 Cloudflare Worker ──────────► static assets (React build, SPA fallback)
     │  /api/*   + X-Proxy-Secret, X-Client-IP
     ▼
 Render web service (FastAPI / uvicorn)
     │  asyncpg over TLS                       │ HTTPS (set creator only)
     ▼                                         ▼
 Neon Postgres                           Anthropic API
```

Local dev mirrors this: Vite's dev server proxies `/api` to `localhost:8000`, so dev is same-origin too.

### 2.1 Auth: server-side sessions, not JWT
**Why sessions:**
- They can be revoked instantly on logout, password change or reset, account deletion, or an admin ban. A JWT stays valid until it expires unless you build a denylist, and a denylist is just a session table with extra steps.
- The token never touches JavaScript, so an XSS bug can't steal it. JWT-in-memory + refresh token still needs a refresh cookie anyway.
- We hit Postgres on every request regardless, so JWT's "no DB lookup" benefit buys nothing here.

**Details:**
- Cookie `__Host-rb_session`, `HttpOnly; Secure; SameSite=Lax; Path=/`.
- Token is 32 random bytes; the DB stores only its SHA-256 hash. Sessions last 30 days and refresh while you keep using them.
- No IP or user agent is stored with the session.
- **CSRF:** SameSite=Lax, plus state-changing requests must carry `X-Requested-With: rb` and a matching `Origin`.
- **Passwords:** argon2id via `argon2-cffi`. Minimum 8 characters, rejected if on a top-10k common-passwords list. No "must contain a symbol" rules (per NIST guidance).
- **Usernames:** 3–20 characters `[A-Za-z0-9_]`, unique case-insensitively. Reserved names (`admin`, `mod`, …) are blocked, and a profanity filter runs after leetspeak normalisation (`0→o`, `1→i`, `3→e`, `4→a`, `5→s`, `@→a`, `$→s`). It deliberately over-blocks, and false positives like "Scunthorpe" are an accepted cost.

### 2.2 Year group maths
```
d               = today's date in Europe/London
academic_start  = d.year if d.month >= 9 else d.year - 1
year_group      = 7 + academic_start - cohort_year
signup:           cohort_year = academic_start - (chosen_year - 7)
graduated:        year_group > 13  → hidden from boards and leagues, can still revise
```
- **Example:** someone signs up in Year 10 on 2026-11-02, so `academic_start` is 2026 and `cohort_year` is 2023. At 00:00 London time on 2027-09-01 they become Year 11.
- **Edge case:** 2027-08-31 23:30 UTC is already 1 September in London (BST), so they are already Year 11 at that moment. Tests cover this, plus Year 13 → graduated and the leap-day and DST boundaries.
- **Correction:** allowed when `year_group_changed_for` is null or older than the current `academic_start`. A correction sets a new `cohort_year` and records the year it happened. Signup doesn't count as a correction.

### 2.3 Spaced repetition: Leitner (not SM-2)
| Box | Comes back after |
|---|---|
| 1 | 1 day |
| 2 | 3 days |
| 3 | 7 days |
| 4 | 14 days |
| 5 | 30 days (maintenance) |

- **Wrong answer** (from any box): back to box 1, due tomorrow.
- **Right answer:** up one box and due after that box's interval. Box 5 stays at box 5.
- **First-ever sighting answered right:** straight to box 4, so it gets one check-in after 2 weeks and easy questions don't flood the review queue.
- Due dates are UK calendar dates, so "due today" is unambiguous.

**Why Leitner:** answers here are right or wrong. SM-2 needs a 0–5 "how well did you know it" score that we don't have, and faking one from response time is noise. Leitner gives the 1/3/7/14-day schedule from the spec directly, a 12-year-old can understand it ("this comes back in 3 days"), and it's trivial to test. All intervals are constants in `domain/srs.py`.

### 2.4 Question types and checking
| Type | Player sees | Correct when |
|---|---|---|
| `mcq` | prompt + 3–5 options, shuffled per attempt (by option ID, not index) | the chosen ID matches |
| `fill_blank` | sentence with one `___` | normalised input is in the accepted-answers list (numeric answers compare as numbers) |
| `order` | 3–6 items, shuffled | the full order matches |
| `match` | 3–6 terms + shuffled definitions | every pair matches |

- Correctness is all-or-nothing for scoring and SRS, but the UI shows partial results like "4/5 in the right place".
- **Answers never reach the client before you answer.** The server checks the answer and only then returns the correct answer, the one-line explanation, and the topic's "learn more" link if you got it wrong.
- **Phone UX** is tap-first: big MCQ buttons, tap-to-place ordering, and tap-a-term-then-tap-its-definition matching. Drag-and-drop on small touchscreens is fiddly and bad for accessibility.

### 2.5 Bot battles
- **Bot accuracy:** your topic accuracy shrunk toward 60% when there's little data: `(correct + 0.6·5) / (answered + 5)`, with ±5% jitter, clamped to 35–92%.
- **Rubber band:** if either side leads by more than 1,000 points, the bot's accuracy on the next question moves 10 points toward closing the gap. That keeps it from being a stomp either way.
- **Bot timing:** log-normal around your median answer time on that topic. Fallbacks when there's no data: MCQ 6s, fill-blank 9s, order/match 14s. Clamped to the range 1.5s to (time limit − 0.5s). When the bot is wrong, it picks a plausible distractor.
- **Server-side plan:** the bot's moves for each question are decided on the server from a seeded RNG. The client gets the bot's timing so it can show "Bot answered!", but only learns whether the bot was right after you answer.
- **Points:** correct = `500 + 500 × max(0, 1 − t/T)`; wrong = 0.
- **Time limits (T):** MCQ 20s, fill-blank 30s, order/match 45s.
- **How `t` is measured:** on the server. A client-reported time is accepted only within `[server_elapsed − 2s, server_elapsed]`. That forgives mobile latency without letting anyone claim they answered in 0s.

### 2.6 Boss battles
- **Unlock:** every *core* question in the topic answered correctly at least once ("Master all 20 core questions to unlock the boss").
- **Format:** 12 questions, hardest first (difficulty 3, then 2). The boss has 1,000 HP and you have 3 hearts.
- **Damage:** correct = 100 damage + up to 50 speed bonus. Wrong = lose a heart.
- **In practice:** roughly 8–10 correct with at most 2 mistakes wins.
- **Rewards:** the first win grants the topic's boss cosmetic (or the next unowned one from the boss pool) plus 150 XP. Rematches give normal XP.

### 2.7 XP, levels, streaks
| Action | XP |
|---|---|
| Correct answer | 10 (2 if you already got that question right today) |
| Correct answer on a due review | +5 bonus |
| Finish a quiz | 20 (+20 if perfect) |
| Battle win / draw / loss | 40 / 25 / 10 |
| Boss defeated (first time) | 150 |
| Daily streak bonus | 5 × min(streak, 10), on your first activity of the day |

- **Levels:** XP needed to reach level L = `50 · L · (L − 1)`. Level 2 = 100, level 5 = 1,000, level 10 = 4,500, level 20 = 19,000. One decent quiz is about 120 XP.
- **What counts toward a streak:** UK days with at least one finished quiz, battle or review session.
- **Freezes:** you hold at most 1. If you have 0, your first activity of each week gives you one. Miss exactly one day while holding a freeze and the freeze is used up but the streak survives. Miss two days and the streak resets.
- **No pressure tactics:** no push notifications and no guilt-trip copy (see §7).
- XP never gates content and gives no gameplay advantage. It only unlocks cosmetics.

### 2.8 Weekly leagues and leaderboards
- **Tiers:** Bronze → Silver → Gold → Sapphire → Diamond. Everyone starts in Bronze.
- **Week:** Monday 00:00 to Sunday 23:59:59, Europe/London. DST-safe.
- **Joining:** you join a league the first time you earn XP in a week, which keeps dead accounts out of groups. You're placed into an existing group for (week, your tier, your year group) with fewer than 20 members, or a new one if they're all full.
- **Ranking:** by weekly XP. Ties go to whoever reached that total first.
- **Promotion and relegation:** promote the top `min(5, n // 4)` and relegate the bottom `min(5, n // 4)`. Nobody gets promoted out of Diamond or relegated out of Bronze.
  - A full 20-person group moves 5 up and 5 down, as in the spec.
  - An 8-person group moves 2 and 2.
  - A group of 3 or fewer moves nobody.
- **Settlement (no cron needed):** the first request after Monday 00:00 settles last week inside one transaction, guarded by a Postgres advisory lock, so it is idempotent. Render's free tier has no cron anyway, and an admin button can force it.
- **Year-group change mid-week (1 Sept):** your current week's group stays the same; next week uses the new year group.
- **Boards:** My league · Weekly (my year / all years) · All-time (my year / all years). Each shows the top 50 plus your own rank. Graduated users are excluded.

### 2.9 Set creator + accuracy pipeline
```
paste notes (≤15k chars)
   → [1] generate      Claude, structured JSON, grounded in notes + spec outline
   → [2] code checks   deterministic, no AI
   → [3] verify        separate Claude call + separate prompt
   → drafts            "Needs checking" badges where flagged
   → [4] human gate    approve / edit / delete — nothing plays until approved
   → live
   → [5] reports       auto-hide after N reports, review queue
```
1. **Generate.** The prompt contains the topic name, spec ref, spec outline and the user's notes. The notes are clearly delimited and treated as data, not instructions. Each question must come back with type, content, answer, a one-line explanation, and a **`source_quote`**: a verbatim snippet from the notes that supports the answer.
2. **Code checks:**
   - `source_quote` must really appear in the notes (whitespace-normalised).
   - MCQ: 3–5 unique options, exactly one correct.
   - Fill-blank: exactly one blank, and the answer appears in the quote.
   - Order and match: 3–6 unique items.
   - Explanation is 200 characters or fewer, and the profanity filter passes.

   Malformed questions are dropped. A missing quote means the question is flagged.
3. **Verify.** A separate call with its own prompt sees the notes, the questions and the claimed answers. It labels each one *supported*, *unsupported*, *ambiguous* or *incorrect*, with a reason. Anything other than *supported* gets a "Needs checking" badge, and the reason is shown in the review UI.
4. **Human gate.** Enforced by a DB `CHECK` constraint as well as app code: a question with `origin='ai'` can't have `status='live'` without `approved_at`. If the user edits a question, it's marked `human_edited` and they can optionally re-run the verifier.
5. **Reports.** Every question has a "Report wrong question" button. A report has a reason plus an optional comment of up to 300 characters, and each user can report a question once. At N distinct reports (default 3) the question is hidden and queued for an admin (official questions) or the set owner (user sets). The admin queue also shows questions below the threshold, since a small user base rarely reaches 3.

**AI config:**
- Prompts live in `backend/app/ai/prompts/generate_questions.md` and `verify_questions.md`, so you can tweak them without touching code.
- Model: `claude-opus-5-5` for both calls by default, configurable via env vars. Adaptive thinking, effort `high`, structured outputs validated by Pydantic, and server-side refusal fallback turned on.
- **Cost estimate (mine, unmeasured):** roughly 10–30p per 10-question batch. Real token counts are logged per job. A per-user daily limit (default 5 batches) and a global daily cap protect the bill.
- **Runs in the background.** Generating and verifying can take 30–90s, so the request returns a job ID and the client polls it.
- **Notes are purged** once every draft in the batch has been reviewed, or after 7 days, whichever comes first. The UI warns: "don't paste anything with your name or personal info in it."
- **Without `ANTHROPIC_API_KEY`**, the set creator still works for writing questions by hand. Only the "Generate" button is disabled.
- **No scraping.** Topics store an optional "learn more" URL, shown after a wrong answer.

**Sets and sharing:**
- Sets are private by default. "Share" creates a join code: 7 characters from an unambiguous alphabet (no 0/O/1/I), which can be rotated or revoked.
- People who join can play the set's *live* questions. They can't edit, can't see drafts, and don't see the creator's username.

---

## 3. Folder structure

```
study/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml             # local Postgres 16 for dev + tests
├── render.yaml                    # Render blueprint (backend)
├── .github/workflows/ci.yml       # lint + pytest + vitest on every push
├── docs/
│   └── PLAN.md                    # this file
├── backend/
│   ├── pyproject.toml             # deps managed with uv
│   ├── alembic.ini
│   ├── migrations/                # Alembic env + versions
│   ├── app/
│   │   ├── main.py                # app factory, middleware, routers
│   │   ├── config.py              # settings from env (+ Neon URL fix-ups for asyncpg)
│   │   ├── db.py                  # async engine + session dependency
│   │   ├── models/                # SQLAlchemy models, one file per area
│   │   ├── schemas/               # Pydantic request/response models
│   │   ├── api/                   # routers: auth, me, home, catalog, play, progress,
│   │   │                          #   exams, cosmetics, leaderboards, sets, admin
│   │   ├── services/              # business logic that touches the DB
│   │   ├── domain/                # pure logic, no DB, heavily unit-tested
│   │   │   ├── calendar.py        # UK day / week / academic year
│   │   │   ├── year_group.py
│   │   │   ├── srs.py             # Leitner
│   │   │   ├── answer_check.py
│   │   │   ├── scoring.py         # battle points, boss damage
│   │   │   ├── bot.py
│   │   │   ├── xp.py              # XP rules + level curve
│   │   │   ├── streaks.py
│   │   │   └── leagues.py         # placement + promotion/relegation
│   │   ├── security/              # passwords, sessions, csrf, rate_limit, profanity
│   │   ├── ai/
│   │   │   ├── client.py
│   │   │   ├── generate.py
│   │   │   ├── verify.py
│   │   │   ├── checks.py          # deterministic validators
│   │   │   └── prompts/
│   │   │       ├── generate_questions.md
│   │   │       └── verify_questions.md
│   │   └── cli.py                 # seed, create-admin, import-topics
│   ├── seed/
│   │   ├── subjects_topics.json
│   │   ├── questions/*.json
│   │   └── cosmetics.json
│   └── tests/
│       ├── unit/                  # domain/ — no DB, fast
│       └── api/                   # endpoint tests against real Postgres
└── frontend/
    ├── package.json
    ├── vite.config.ts             # dev proxy /api → localhost:8000
    ├── wrangler.jsonc             # Worker: static assets + /api proxy
    ├── worker/index.ts            # the proxy (~30 lines)
    ├── index.html
    ├── public/
    │   ├── _headers               # CSP + security headers
    │   └── cosmetics/             # layered SVG placeholders
    └── src/
        ├── main.tsx, App.tsx, routes.tsx
        ├── api/                   # fetch wrapper, OpenAPI-generated types, query hooks
        ├── components/            # Avatar, BottomNav, Timer, ProgressBar, …
        │   └── questions/         # Mcq, FillBlank, Order, Match
        ├── features/              # auth, home, play, weak-spots, sets,
        │                          #   leaderboards, avatar, settings, admin
        ├── lib/
        └── test/
```

**Frontend libs:**
- React Router and TanStack Query.
- Tailwind CSS with a system font stack, so no Google Fonts and no third-party requests at all.
- Vitest + React Testing Library + MSW for tests.
- `openapi-typescript` generates frontend types from FastAPI's OpenAPI schema, so the frontend can't silently drift from the backend.

**Backend libs:**
- fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic v2, pydantic-settings, argon2-cffi, anthropic.
- Dev and test: pytest, pytest-asyncio, httpx, ruff.

---

## 4. Database schema

**Conventions:**
- `bigint identity` PKs, except UUIDs where an ID appears in URLs (play sessions, generation jobs).
- Enum-like columns are `text` + `CHECK` constraints, which are easier to evolve in Alembic than native Postgres enums.
- All timestamps are `timestamptz` (UTC). "UK day/week" logic lives in one place (`domain/calendar.py`, using `Europe/London`).

### Accounts
**users**: the only per-person table, and the only personal-ish data in the system
| column | type | notes |
|---|---|---|
| id | bigint PK | |
| username | text | unique on `lower(username)` |
| password_hash | text | argon2id |
| recovery_code_hash | text | argon2id |
| cohort_year | smallint | calendar year of the September they started Year 7 |
| year_group_changed_for | smallint null | academic year of their last correction |
| is_admin | bool | only settable via CLI, never via the API |
| total_xp | int | cached sum of `xp_events` |
| league_tier | smallint | 0 Bronze … 4 Diamond |
| streak_current, streak_best | int | |
| streak_last_day | date null | UK date of last qualifying activity |
| streak_freezes | smallint | 0 or 1 |
| streak_freeze_week | date null | week a freeze was last granted |
| created_at | timestamptz | |

**auth_sessions**: `id`, `user_id` → users (cascade), `token_hash` (unique), `created_at`, `expires_at`, `last_seen_at`.

**rate_limit_hits**: `key` (e.g. `login:user:abc`, `signup:ip:<hmac>`), `window_start`, `count`. PK is `(key, window_start)`. Old rows are purged.

### Content
> **Changed after approval** to fit the school's topic file. Topics are shared across subjects (AQA Combined Science reuses the separate sciences' topics, e.g. `sci-bio-cells`), boards include Eduqas and OCR Cambridge Nationals, and subtopics carry "(higher)" / "(triple only)" tags.

**subjects**: `id`, `slug` (unique), `name`, `qualification` (free text, e.g. "GCSE (triple)", "Cambridge National Level 1/2"), `exam_board` (free text, admin-managed), `spec_code`, `spec_url`, `spec_url_alt`, `board_confidence` (`stated`/`inferred`), `admin_notes`, `sort_order`, `is_active`.

**topics**: `id`, `slug` (unique; the `id` from the topic file), `name`, `subtopics` (jsonb list of `{name, higher_only, triple_only}`, which also grounds the AI), `learn_more_url` (null; https only), `boss_cosmetic_id` (null), `is_active`.

**subject_topics** (many-to-many): `subject_id`, `topic_id`, `display_name` (e.g. "Biology 1: Cell biology" under Combined Science), `spec_ref`, `sort_order`, `excludes_triple_only` (true for Combined Science links).

- Questions attach to the **topic**, so Combined and triple students share one question bank and one set of progress stats.
- Playing via a Combined Science link hides `triple_only` questions.
- A Foundation/Higher toggle on the topic page (remembered on the device, not stored on the server) hides `higher_only` questions.

**question_sets** (user-made only): `id`, `owner_id` → users (cascade), `topic_id`, `title`, `join_code` (null, unique), `created_at`, `updated_at`.

**set_members**: `set_id`, `user_id`, `joined_at`. PK is `(set_id, user_id)`.

**questions**
| column | type | notes |
|---|---|---|
| id | bigint PK | |
| topic_id | FK | |
| set_id | FK null | **null = official question bank** |
| type | text | `mcq` / `fill_blank` / `order` / `match` |
| prompt | text | |
| content | jsonb | what the player sees (options / items / pairs), validated by Pydantic per type |
| answer | jsonb | **server-only**, never serialised to clients before answering |
| explanation | text | one line, ≤200 chars, required |
| subtopic | text null | which subtopic it covers |
| difficulty | smallint | 1–3 |
| is_core | bool | official only; core set gates the boss |
| higher_only | bool | Higher-tier content |
| triple_only | bool | hidden when playing via Combined Science |
| case_sensitive | bool | fill-blank only |
| status | text | `draft` / `live` / `hidden` / `archived` |
| origin | text | `seed` / `admin` / `manual` / `ai` |
| verification | text | `unchecked` / `passed` / `needs_checking` |
| verification_note | text null | why it was flagged |
| source_quote | text null | AI-generated only |
| human_edited | bool | |
| report_count | int | distinct open reports |
| generation_job_id | FK null | |
| approved_by, approved_at | null | |
| created_at, updated_at | timestamptz | |

`CHECK (NOT (origin = 'ai' AND status = 'live' AND approved_at IS NULL))`. Questions that someone has already answered are archived instead of deleted, so stats stay correct. Drafts are hard-deleted.

**generation_jobs**: `id` (uuid), `user_id`, `set_id`, `status` (`queued`/`generating`/`verifying`/`done`/`failed`), `notes` (null; purged), `notes_purged_at`, `requested_count`, `requested_types`, `model`, `input_tokens`, `output_tokens`, `error`, `created_at`, `finished_at`.

**question_reports**: `id`, `question_id`, `reporter_id` (set to null if the account is deleted), `reason` (`wrong_answer`/`ambiguous`/`typo`/`inappropriate`/`other`), `comment` (≤300), `status` (`open`/`upheld`/`dismissed`), `resolved_by`, `resolved_at`, `created_at`. Unique on `(question_id, reporter_id)`.

### Play and progress
**play_sessions**: `id` (uuid), `user_id`, `mode` (`quiz`/`battle`/`boss`/`review`), `subject_id` (null; the subject context, which decides triple-only filtering), `topic_id` (null), `set_id` (null), `include_higher`, `status` (`active`/`finished`/`abandoned`), `question_count`, `current_position`, `user_score`, `bot_score`, `bot_profile` (jsonb: name, accuracy, seed), `boss_hp`, `hearts`, `result` (`win`/`loss`/`draw`, null), `xp_awarded`, `started_at`, `finished_at`.

**session_answers**: this is also the answer log behind all accuracy stats.
- Columns: `session_id`, `position`, `question_id`, `user_id` and `topic_id` (both denormalised for fast stats), `shown` (jsonb: the shuffled order shown), `served_at`, `answered_at`, `response` (jsonb), `is_correct`, `response_ms`, `points`, `bot_correct`, `bot_ms`, `bot_points`.
- PK is `(session_id, position)`, which also makes double-taps harmless. Index on `(user_id, topic_id, answered_at)`.

**question_reviews** (Leitner state): `user_id`, `question_id`, `box` (1–5), `due_on` (date), `times_right`, `times_wrong`, `updated_at`. PK is `(user_id, question_id)`; index on `(user_id, due_on)`.

**topic_progress**: `user_id`, `topic_id`, `last_played_at` (drives quick launch), `boss_unlocked_at`, `boss_defeated_at`. PK is `(user_id, topic_id)`.

**exam_dates**: `id`, `user_id`, `subject_id`, `label` (≤40, optional, e.g. "Paper 1"), `exam_date`, `created_at`.

### Rewards and ranking
**xp_events** (ledger): `id`, `user_id`, `amount`, `source` (`answer`/`quiz`/`battle`/`boss`/`streak`/`review`), `session_id` (null), `created_at`. Index on `(user_id, created_at)`.

**cosmetics**: `id`, `slot` (`hat`/`background`/`frame`), `key` (asset filename), `name`, `unlock_type` (`default`/`level`/`streak`/`boss`), `unlock_value` (null), `sort_order`.

**user_cosmetics**: `user_id`, `cosmetic_id`, `unlocked_at`.

**user_equipped**: `user_id`, `slot`, `cosmetic_id`. PK is `(user_id, slot)`. A composite FK to `user_cosmetics` means you can only equip what you own.

**league_weeks**: `week_start` (date PK), `settled_at` (null).

**league_groups**: `id`, `week_start`, `tier`, `year_group`, `created_at`.

**league_members**: `group_id`, `user_id`, `week_start` (denormalised), `weekly_xp`, `last_xp_at` (tiebreak), `outcome` (`promoted`/`stayed`/`relegated`, null). PK is `(group_id, user_id)`; unique on `(user_id, week_start)`.

---

## 5. API routes

Everything lives under `/api`. Access is one of: **public**, **user** (logged in), **owner** (owns the set), **member** (joined the set), **admin**. All state-changing routes need the CSRF header.

### Auth
| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/auth/signup` | public | username, password, year_group (7–13) → sets cookie, returns the recovery code **once** |
| POST | `/auth/login` | public | |
| POST | `/auth/logout` | user | |
| POST | `/auth/recover` | public | username + recovery code + new password → logs in, returns a new recovery code |
| GET | `/auth/username-ideas` | public | random safe username suggestions |

### Me and settings
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/me` | user | username, year group / graduated, level, XP, tier, is_admin |
| PATCH | `/me/year-group` | user | once per academic year |
| POST | `/me/password` | user | change password; logs out other sessions |
| POST | `/me/recovery-code` | user | regenerate (needs current password) |
| DELETE | `/me` | user | delete account and all data (needs password) |

### Home, exams, catalogue
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/home` | user | avatar, XP/level, streak, quick-launch topics (recent + weakest), due review count, exam countdowns. **One call** so the phone does one round trip |
| GET | `/exams` | user | |
| POST | `/exams` | user | subject_id, date, optional label |
| DELETE | `/exams/{id}` | user | |
| GET | `/subjects` | user | |
| GET | `/subjects/{id}/topics` | user | topics with your accuracy + boss state |
| GET | `/topics/{id}` | user | |

### Play
| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/play` | user | start `{mode: quiz\|battle\|boss\|review, topic_id? \| set_id?}` → session + first question (no answer) |
| GET | `/play/{session_id}` | user | resume after refresh |
| POST | `/play/{session_id}/answer` | user | → correct?, correct answer, explanation, learn-more link (if wrong), points, bot's result, next question |
| POST | `/play/{session_id}/finish` | user | → summary, XP gained, level-ups, unlocks, streak update |

### Progress, avatar, leaderboards
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/progress/weak-spots` | user | accuracy per topic over the last 60 days (min 5 answers), worst first |
| GET | `/cosmetics` | user | all cosmetics with owned/locked status + unlock hint |
| PUT | `/avatar` | user | equip `{slot: cosmetic_id}` |
| GET | `/leaderboards/league` | user | my group, promotion/relegation zones, time left, last week's result |
| GET | `/leaderboards/weekly?scope=year\|all` | user | top 50 + my rank |
| GET | `/leaderboards/all-time?scope=year\|all` | user | top 50 + my rank |

### Sets, AI, reports
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/sets` | user | mine + joined |
| POST | `/sets` | user | `{title, topic_id}` |
| GET | `/sets/{id}` | owner/member | members only see live questions |
| PATCH | `/sets/{id}` | owner | |
| DELETE | `/sets/{id}` | owner | |
| POST | `/sets/{id}/share` | owner | create or rotate the join code |
| DELETE | `/sets/{id}/share` | owner | revoke the code |
| POST | `/sets/join` | user | `{code}` |
| DELETE | `/sets/{id}/membership` | member | leave |
| POST | `/sets/{id}/generate` | owner | `{notes, count, types}` → `202` + job id |
| GET | `/generation-jobs/{id}` | owner | status + drafts with verification flags |
| POST | `/sets/{id}/questions` | owner | add a question by hand |
| PATCH | `/questions/{id}` | owner/admin | edit |
| POST | `/questions/{id}/approve` | owner/admin | draft → live |
| POST | `/questions/{id}/recheck` | owner | re-run the verifier after an edit |
| DELETE | `/questions/{id}` | owner/admin | |
| POST | `/questions/{id}/report` | anyone who can see it | `{reason, comment?}` |

### Admin and system
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/admin/reports` | admin | reported questions, most-reported first |
| POST | `/admin/questions/{id}/resolve` | admin | restore / keep hidden / edit + uphold or dismiss reports |
| CRUD | `/admin/subjects`, `/admin/topics` | admin | official topic list |
| POST | `/admin/topics/import` | admin | bulk import your spec topic lists (CSV or JSON) |
| CRUD | `/admin/questions` | admin | official questions |
| POST | `/admin/leagues/settle` | admin | force league settlement (normally automatic) |
| GET | `/health` | public | DB ping for Render health checks |

### Frontend screens
- **Bottom nav:** Home · Revise · Create · Ranks · Me.
- **Screens:** login / signup / recover, home, subject → topic picker, topic page (quiz / battle / boss / your accuracy), play runner, results, weak spots, leaderboards, wardrobe, set list, set detail (generate, review drafts, share), join by code, settings (year group, password, recovery code, exams, delete account), and admin.

---

## 6. Phases

Each phase ends with a stop, a summary, and run/test steps.

**Phase 1: scaffold** ✅ done
- Repo layout and `.env.example`.
- FastAPI app with `/api/health`.
- Config, including Neon URL normalisation: asyncpg can't read `sslmode=` and Neon's pooler needs the prepared-statement cache off.
- All models + the initial Alembic migration.
- docker-compose Postgres.
- Vite/React/TS/Tailwind app shell with bottom nav and route stubs.
- Worker proxy + `wrangler.jsonc`.
- CI workflow and a README skeleton.

**Phase 2: accounts**
- Signup, login, logout, recovery codes.
- Sessions, CSRF, rate limits, profanity filter, username ideas.
- Year group calculation, the settings correction rule, and account deletion.
- Auth screens.
- Tests: auth, year group (including September rollover edge cases), rate limits.
- **First deploy smoke test** on Render + Neon + Cloudflare.

**Phase 3: content + quick quiz**
- Subjects, topics and questions.
- Seed script: 3 topics, around 60 hand-checked questions covering all 4 types.
- Admin topic CRUD + bulk import, and the CLI to create the admin account.
- Answer checking.
- Quiz runner UI for all 4 types, with explanations and learn-more links.
- Tests: answer checking, and that answers never leak before you answer.

**Phase 4: spaced repetition + home**
- Leitner scheduling and review mode.
- Weak spots page.
- Home screen: quick launch, due count, exam countdowns (XP and avatar are placeholders until Phase 6).
- Tests: SRS scheduling.

**Phase 5: battles**
- Bot engine, timers, scoring, battle UI.
- Boss unlock rule, HP/hearts UI, reward hook.
- Tests: scoring, bot bounds and determinism, boss rules.

**Phase 6: progression + ranking**
- XP ledger, levels, cosmetics + SVG placeholders, wardrobe.
- Streaks and freezes.
- Leaderboards and weekly leagues with automatic settlement.
- Tests: XP, streaks, league promotion/relegation (including ties, small groups, edge tiers and the DST week).

**Phase 7: set creator + AI**
- Sets CRUD and join codes.
- Generation job, code checks, verifier, and the draft review UI.
- Report button with auto-hide, and the admin reports queue.
- Tests: the Anthropic client is mocked; drafts are unplayable until approved, the DB constraint holds, and auto-hide fires at N.

**Phase 8: polish + ship**
- Loading, empty and error states; accessibility pass; PWA manifest ("add to home screen").
- Plain-English privacy page.
- Frontend tests for key flows, plus filling test gaps.
- `render.yaml`, final Worker config, full README deploy steps.

---

## 7. Privacy and safety

**Stored per user:**
- Username, argon2 password hash, recovery-code hash.
- Cohort year and the year-group-change marker.
- Game state: XP, streak, tier, cosmetics, answers, review schedule, exam dates, sets.

That's everything.

**Never stored:** email, real name, school, date of birth, raw IP addresses, user agents, or analytics. The frontend loads no third-party scripts or fonts.

**Account deletion** is a hard delete of everything. Reports the user filed are kept, but with `reporter_id` set to null.

**UK Children's Code:**
- The ICO's Age Appropriate Design Code likely applies to an app aimed at under-18s in the UK.
- The design already fits it: minimal data, private by default, no profiling, and no prompts to share data.
- Streaks and leagues are engagement mechanics, so they're kept gentle: freezes, no notifications, no FOMO copy.
- You'll want a short plain-English privacy notice before launch. This is not legal advice.

**Anthropic:**
- Pasted notes are sent to the Anthropic API for set generation. Say so in the privacy notice.
- Check Anthropic's usage policy on products used by minors.

**Exam board specs** are copyrighted. Seed topic names, spec refs and short outlines in your own words, not the spec text itself.

**Child-safety guardrails:** no messaging, no profiles, and no friend lists. Set creators' usernames are hidden from people who join their sets.

---

## 8. Environment variables (`.env.example`)

| Var | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | backend | Neon **pooled** connection string (the app uses it) |
| `DATABASE_URL_DIRECT` | backend | optional Neon direct string for migrations; falls back to `DATABASE_URL` |
| `SECRET_KEY` | backend | HMAC key for IP hashing etc. |
| `PROXY_SHARED_SECRET` | backend + Worker | proves a request came through the Worker |
| `FRONTEND_ORIGIN` | backend | CORS + Origin checks |
| `ENVIRONMENT` | backend | `dev` / `prod` |
| `ANTHROPIC_API_KEY` | backend | optional; without it the AI generate button is disabled |
| `ANTHROPIC_MODEL_GENERATE` | backend | default `claude-opus-5-5` |
| `ANTHROPIC_MODEL_VERIFY` | backend | default `claude-opus-5-5` |
| `AI_BATCHES_PER_USER_PER_DAY` | backend | default 5 |
| `AI_BATCHES_GLOBAL_PER_DAY` | backend | default 200 |
| `REPORT_HIDE_THRESHOLD` | backend | default 3 |
| `BACKEND_URL` | Worker | Render service URL |

**Hosting notes:**
- **Render's free tier** sleeps after about 15 minutes idle, so the first student of the day waits roughly a minute while it wakes. The $7/month starter instance fixes that.
- **Migrations on the free tier** run in the start command, because pre-deploy commands are a paid feature.
- **Neon's free tier** also suspends when idle but wakes much faster.

---

## 9. Open questions (my defaults in bold)

1. **Hosting:** Cloudflare **Workers static assets** (recommended) or Pages?
2. **Recovery codes:** **yes** (recommended), or no password recovery at all?
3. **Demo seed content:** ✅ AQA Biology – Cell biology (`sci-bio-cells`), AQA Chemistry – Atomic structure and the periodic table (`sci-chem-atomic`), and **Edexcel** History – Weimar and Nazi Germany 1918–39 (`hist-weimar-nazi`). Switched from AQA History because the school does Edexcel.
4. **Report threshold N:** **3**?
5. **Do you own a domain?** If yes, the app can use `app.` and `api.` subdomains instead of `workers.dev` (the Worker proxy works either way).

---

## 10. Follow-ups from the topic file (handled in Phase 3)

- **French and German** have no topics yet; the file says to clone the Spanish tree. The Phase 3 importer will clone it with French/German grammar subtopics, flagged for you to check.
- **English Literature:** confirm which Shakespeare play and poetry cluster your cohort studies, then trim the unused texts.
- **Boards marked `inferred`** (RS, Business, Media, Food, D&T): check against the specs. They're stored with `board_confidence = inferred` so the admin screen can flag them.
- **Spec refs** were written from knowledge of each spec, not copied, so check them before relying on them.
