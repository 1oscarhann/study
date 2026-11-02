# Deploying Revision Battle

Three free accounts, about 20 minutes. Order matters, because each step needs a URL from the one before.

```
Neon (database)  →  Render (API)  →  Cloudflare (site + /api proxy)  →  back to Render to set FRONTEND_ORIGIN
```

Never paste connection strings or secrets into chat, issues or commits. They only go into the Render and Cloudflare dashboards.

---

## 1. Neon: the database

1. Sign up at neon.tech and create a project called `revision-battle`. Pick the **AWS Europe West 2 (London)** region (closest to your users).
2. Open **Connect** on the project dashboard.
3. With **Connection pooling ON**, copy the connection string. This is `DATABASE_URL`. Its host contains `-pooler`.
4. Turn pooling **OFF** and copy the string again. This is `DATABASE_URL_DIRECT`, used for migrations.

Paste them as-is. The app handles `sslmode=require` and Neon's PgBouncer quirks itself.

## 2. Render: the API

You can do this yourself (option A), or ask Claude to create the service through the Render connector (option B).

**Option A: Blueprint**

1. In the Render dashboard, go to **New → Blueprint** and connect the GitHub repo `1oscarhann/study`. It reads `render.yaml`.
2. Fill in the environment variables it asks for:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon pooled string |
| `DATABASE_URL_DIRECT` | Neon direct string |
| `PROXY_SHARED_SECRET` | Generate one with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` and keep it for step 3 |
| `FRONTEND_ORIGIN` | `https://example.com` for now; the real value comes in step 4 |
| `ANTHROPIC_API_KEY` | Leave empty for now (only AI question drafting needs it) |

`SECRET_KEY` is generated automatically.

3. Wait for the deploy. On boot it runs the database migrations, then starts the API.
4. Note the service URL (e.g. `https://revision-battle-api.onrender.com`) and open `/api/health` on it. You should see `{"status":"ok","db":"ok"}`.

**Option B: Claude creates it**

Claude creates the web service on your Render account (free plan, Frankfurt). You then paste the Neon strings and the secret into its **Environment** tab, and it redeploys.

> The free plan sleeps after about 15 minutes idle, so the first visit after that takes up to a minute. The app shows "Waking up the server…" while it waits. The $7/month Starter plan removes the sleep.

## 3. Cloudflare: the site and the `/api` proxy

1. Put your Render URL in `frontend/wrangler.jsonc` under `vars.BACKEND_URL`, then commit and push. Or ask Claude to do it.
2. In the Cloudflare dashboard, go to **Workers & Pages → Create → Import a repository** and pick `1oscarhann/study`. Use these settings:

| Setting | Value |
|---|---|
| Project name | `revision-battle` (must match `name` in `wrangler.jsonc`) |
| Root directory | `frontend` |
| Build command | `npm run build` |
| Deploy command | `npx wrangler deploy` |

3. After the first deploy, open the Worker and go to **Settings → Variables and Secrets**. Add a **Secret** named `PROXY_SHARED_SECRET` with the same value you gave Render.
4. Note the site URL: `https://revision-battle.<your-subdomain>.workers.dev`.

If you'd rather deploy from your own computer:

```bash
cd frontend && npm ci
```

```bash
cd frontend && npx wrangler login
```

```bash
cd frontend && npx wrangler secret put PROXY_SHARED_SECRET
```

```bash
cd frontend && npm run cf:deploy
```

## 4. Back to Render

Set `FRONTEND_ORIGIN` to the exact site URL from step 3: `https://…workers.dev`, with no trailing slash. Render redeploys automatically.

## 5. Smoke test

From a checkout of the repo:

```bash
cd backend && uv run python scripts/smoke_test.py https://revision-battle.<your-subdomain>.workers.dev https://<your-service>.onrender.com
```

All 9 checks should pass. It confirms:
- the site and its routes load
- the API answers through the Worker
- Render refuses direct traffic
- the login cookie is the secure first-party kind
- a throwaway account can sign up, log in and delete itself (so nothing is left behind)

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Site says **Can't reach the server** for over a minute | `BACKEND_URL` in `wrangler.jsonc` is wrong, or the Render deploy failed (check its logs). |
| Every action fails with **Request blocked (unexpected origin)** | `FRONTEND_ORIGIN` on Render doesn't exactly match the site URL. |
| `/api/...` through the site returns **Forbidden.** | `PROXY_SHARED_SECRET` differs between Render and Cloudflare. |
| Render deploy fails on `alembic upgrade head` | `DATABASE_URL_DIRECT` (or `DATABASE_URL`) is wrong, or the Neon project is suspended. |
| Login works but you're logged out on refresh (iPhone) | You're calling the Render URL directly instead of the site URL. Always use the `workers.dev` address. |
