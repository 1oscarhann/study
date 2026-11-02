/**
 * Thin fetch wrapper. Always same-origin: in dev Vite proxies /api to the backend,
 * in prod the Cloudflare Worker does. The session cookie is httpOnly, so JS never
 * sees it; the browser just sends it.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  /** Which form field the error is about, when the API says so. */
  readonly field: string | null;

  constructor(status: number, detail: string, code: string | null = null, field: string | null = null) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

type JsonBody = Record<string, unknown> | unknown[];

export interface ApiOptions extends Omit<RequestInit, "body"> {
  json?: JsonBody;
}

function describe(status: number, data: unknown): ApiError {
  if (data && typeof data === "object" && "detail" in data) {
    const body = data as { detail: unknown; code?: unknown; field?: unknown };
    const detail = typeof body.detail === "string" ? body.detail : "Something went wrong.";
    return new ApiError(
      status,
      detail,
      typeof body.code === "string" ? body.code : null,
      typeof body.field === "string" ? body.field : null,
    );
  }
  if (status === 502 || status === 503) {
    return new ApiError(status, "The server is waking up. Try again in a moment.");
  }
  return new ApiError(status, "Something went wrong. Please try again.");
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

  if (response.status === 204) return undefined as T;
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data: unknown = isJson ? await response.json() : await response.text();
  if (!response.ok) throw describe(response.status, data);
  return data as T;
}

/** The message to show for any thrown error. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Can't reach the server. Check your connection and try again.";
}
