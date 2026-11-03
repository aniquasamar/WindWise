// Thin fetch wrapper: JSON in, typed errors out. The API's own error shape is
// {"error": {"code", "message", "request_id"}}.

export class ApiError extends Error {
  kind: "network" | "http";
  status: number | null;
  code: string;
  requestId: string | null;

  constructor(kind: "network" | "http", message: string, status: number | null, code: string, requestId: string | null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export function apiUrl(path: string, params: Record<string, string | number | null | undefined> = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") search.set(key, String(value));
  }
  const query = search.toString().replace(/%3A/g, ":");
  return query ? `${path}?${query}` : path;
}

interface ErrorBody {
  error?: { code?: string; message?: string; request_id?: string | null };
}

export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { headers: { Accept: "application/json" }, signal });
  } catch (err) {
    if (signal?.aborted) throw err;
    throw new ApiError("network", "We couldn\u2019t reach the server.", null, "network_error", null);
  }
  if (!response.ok) {
    let body: ErrorBody = {};
    try {
      body = (await response.json()) as ErrorBody;
    } catch {
      // not JSON: fall through to the generic message
    }
    throw new ApiError(
      "http",
      body.error?.message ?? `The server answered with an error (${response.status}).`,
      response.status,
      body.error?.code ?? "http_error",
      body.error?.request_id ?? response.headers.get("X-Request-ID"),
    );
  }
  return (await response.json()) as T;
}