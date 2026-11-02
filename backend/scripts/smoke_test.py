"""Check a live deployment end to end.

    uv run python scripts/smoke_test.py https://revision-battle.<you>.workers.dev https://<service>.onrender.com

It checks the site loads, the API answers through the Worker, the Render URL refuses
direct traffic, and that a throwaway account can sign up, log in and delete itself (so it
leaves nothing behind). Exits non-zero if anything fails.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security.usernames import username_ideas

PASSWORD = "smoke test passphrase " + secrets.token_hex(4)


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"{'✅' if ok else '❌'} {label}{f'  ({detail})' if detail and not ok else ''}")
    return ok


def main(site: str, backend: str) -> int:
    site, backend = site.rstrip("/"), backend.rstrip("/")
    results: list[bool] = []
    # The free Render instance may be asleep; give it time to wake.
    timeout = httpx.Timeout(90.0)
    headers = {"X-Requested-With": "rb", "Origin": site}

    with httpx.Client(timeout=timeout, follow_redirects=False) as raw:
        r = raw.get(f"{backend}/api/health")
        results.append(check("Render health check", r.status_code == 200, r.text[:200]))
        r = raw.get(f"{backend}/api/me")
        results.append(
            check("Render refuses direct traffic (403)", r.status_code == 403, str(r.status_code))
        )

    with httpx.Client(base_url=site, timeout=timeout, headers=headers) as c:
        r = c.get("/")
        site_ok = r.status_code == 200 and "Revision Battle" in r.text
        results.append(check("Site loads", site_ok, str(r.status_code)))
        r = c.get("/revise")
        results.append(check("SPA routes fall back to the app", r.status_code == 200))
        r = c.get("/api/health")
        results.append(
            check("API reachable through the Worker", r.json().get("db") == "ok", r.text[:200])
        )

        username = username_ideas(1)[0]  # always passes the username rules
        r = c.post(
            "/api/auth/signup",
            json={"username": username, "password": PASSWORD, "year_group": 10},
        )
        cookie = r.headers.get("set-cookie", "")
        results.append(check("Signup works", r.status_code == 201, r.text[:200]))
        secure_cookie = (
            cookie.startswith("__Host-rb_session=") and "Secure" in cookie and "HttpOnly" in cookie
        )
        results.append(
            check(
                "Session cookie is first-party, __Host-, Secure, HttpOnly",
                secure_cookie,
                cookie[:120],
            )
        )
        r = c.get("/api/me")
        results.append(check("Logged in after signup", r.status_code == 200, r.text[:200]))
        r = c.request("DELETE", "/api/me", json={"password": PASSWORD})
        results.append(check("Test account deleted again", r.status_code == 204, r.text[:200]))

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
