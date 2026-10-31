import { API_BASE_URL } from "./config";

export { safeNextPath } from "./navigation";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const GENERIC_ERROR = "ارتباط با سرور برقرار نشد. دوباره تلاش کنید.";

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    // Pydantic validation errors: show the first Persian message if present
    if (Array.isArray(body?.detail)) {
      const msg = body.detail.map((d: { msg?: string }) => d.msg ?? "").find((m: string) => /[\u0600-\u06FF]/.test(m));
      if (msg) return msg.replace(/^Value error, /, "");
    }
  } catch {
    // ignore non-JSON bodies
  }
  if (res.status === 422) return "اطلاعات واردشده معتبر نیست.";
  if (res.status >= 500) return "خطای سرور. کمی بعد دوباره تلاش کنید.";
  return GENERIC_ERROR;
}

/**
 * Fetch wrapper for the backend API.
 * - Session lives in an HttpOnly cookie (credentials: include); no token in JS storage.
 * - Sends X-Requested-With, required by the backend CSRF check on mutations.
 * - On 401 outside the login call, sends the user to the login page.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const isForm = typeof FormData !== "undefined" && init?.body instanceof FormData;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        // For FormData the browser sets multipart Content-Type with boundary
        ...(isForm ? {} : { "Content-Type": "application/json" }),
        "X-Requested-With": "fetch",
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, GENERIC_ERROR);
  }

  if (res.status === 401 && path !== "/api/auth/login" && typeof window !== "undefined") {
    const here = window.location.pathname + window.location.search;
    if (!window.location.pathname.startsWith("/login")) {
      // Hard navigation on purpose: drop all in-memory state of the expired session
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign(`/login?next=${encodeURIComponent(here)}`);
    }
  }
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Absolute URL for an authenticated API resource (e.g. a private image). */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}
