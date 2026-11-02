/**
 * Thin fetch wrapper. Always same-origin: in dev Vite proxies /api to the backend,
 * in prod the Cloudflare Worker does. The session cookie is httpOnly, so JS never
 * sees it; the browser just sends it.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type JsonBody = Record<string, unknown> | unknown[];

export interface ApiOptions extends Omit<RequestInit, "body"> {
  json?: JsonBody;
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { json, headers, ...rest } = options;
  const finalHeaders = new Headers(headers);
  finalHeaders.set("Accept", "application/json");
  // CSRF guard: the backend requires this header on state-changing requests.
  finalHeaders.set("X-Requested-With", "rb");
  if (json !== undefined) finalHeaders.set("Content-Type", "application/json");

  const response = await fetch(`/api${path}`, {
    ...rest,
    headers: finalHeaders,
    credentials: "same-origin",
    body: json === undefined ? undefined : JSON.stringify(json),
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data: unknown = isJson ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = isJson && data && typeof data === "object" && "detail" in data
      ? (data as { detail: unknown }).detail
      : data;
    throw new ApiError(response.status, detail);
  }
  return data as T;
}
