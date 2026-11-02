/**
 * Cloudflare Worker: serves the React build and proxies /api/* to the FastAPI backend
 * on Render. Putting the API on the same origin as the site makes the session cookie
 * first-party, which Safari / iOS require (they block third-party cookies).
 *
 * Only /api/* reaches this code (see run_worker_first in wrangler.jsonc).
 */

// Headers a client must never be able to set themselves: the backend trusts these
// only because this Worker sets them.
const CLIENT_FORBIDDEN = ["x-proxy-secret", "x-client-ip", "x-forwarded-for", "x-real-ip"];
const HOP_BY_HOP = [
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
];

export function isApiPath(pathname: string): boolean {
  return pathname === "/api" || pathname.startsWith("/api/");
}

export async function proxyToBackend(request: Request, env: Env): Promise<Response> {
  const incoming = new URL(request.url);
  const target = new URL(incoming.pathname + incoming.search, env.BACKEND_URL);

  const headers = new Headers(request.headers);
  for (const name of [...CLIENT_FORBIDDEN, ...HOP_BY_HOP]) headers.delete(name);
  headers.set("x-proxy-secret", env.PROXY_SHARED_SECRET);
  const clientIp = request.headers.get("cf-connecting-ip");
  if (clientIp) headers.set("x-client-ip", clientIp);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      redirect: "manual",
    });
  } catch {
    return Response.json(
      { detail: "The server is waking up or unavailable. Try again in a moment." },
      { status: 502, headers: { "cache-control": "no-store" } },
    );
  }

  // Re-wrap so headers are mutable; Set-Cookie and everything else pass through.
  const response = new Response(upstream.body, upstream);
  response.headers.set("cache-control", "no-store");
  return response;
}

export default {
  async fetch(request, env): Promise<Response> {
    if (isApiPath(new URL(request.url).pathname)) {
      return proxyToBackend(request, env);
    }
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
