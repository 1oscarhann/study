// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

import worker, { isApiPath } from "./index";

const env = {
  BACKEND_URL: "https://api.example.onrender.com",
  PROXY_SHARED_SECRET: "s3cret",
  ASSETS: { fetch: vi.fn(async () => new Response("<html>app</html>")) },
} as unknown as Env;

function call(request: Request) {
  // The handler only uses request + env.
  return worker.fetch(request as never, env);
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("isApiPath", () => {
  it.each([
    ["/api", true],
    ["/api/health", true],
    ["/apiary", false],
    ["/", false],
    ["/revise", false],
  ])("%s -> %s", (path, expected) => {
    expect(isApiPath(path)).toBe(expected);
  });
});

describe("worker", () => {
  it("serves static assets for non-API paths", async () => {
    const res = await call(new Request("https://app.example/revise"));
    expect(await res.text()).toContain("app");
    expect(env.ASSETS.fetch).toHaveBeenCalledOnce();
  });

  it("forwards /api requests with the shared secret and real client IP", async () => {
    const upstream = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      Response.json({ status: "ok" }),
    );
    vi.stubGlobal("fetch", upstream);

    const res = await call(
      new Request("https://app.example/api/health?x=1", {
        headers: {
          "cf-connecting-ip": "203.0.113.7",
          // A client trying to spoof the trusted headers:
          "x-proxy-secret": "guess",
          "x-client-ip": "1.2.3.4",
          cookie: "__Host-rb_session=abc",
        },
      }),
    );

    expect(res.status).toBe(200);
    expect(res.headers.get("cache-control")).toBe("no-store");
    const [target, init] = upstream.mock.calls[0]!;
    expect(String(target)).toBe("https://api.example.onrender.com/api/health?x=1");
    const sent = new Headers(init?.headers);
    expect(sent.get("x-proxy-secret")).toBe("s3cret");
    expect(sent.get("x-client-ip")).toBe("203.0.113.7");
    expect(sent.get("cookie")).toBe("__Host-rb_session=abc");
  });

  it("passes Set-Cookie back to the browser", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response("{}", {
          headers: { "set-cookie": "__Host-rb_session=new; HttpOnly; Secure; Path=/; SameSite=Lax" },
        }),
      ),
    );
    const res = await call(new Request("https://app.example/api/auth/login", { method: "POST", body: "{}" }));
    expect(res.headers.get("set-cookie")).toContain("__Host-rb_session=new");
  });

  it("returns a friendly 502 when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new Error("connection refused"))));
    const res = await call(new Request("https://app.example/api/health"));
    expect(res.status).toBe(502);
    expect(await res.json()).toEqual({ detail: expect.stringContaining("waking up") });
  });
});
