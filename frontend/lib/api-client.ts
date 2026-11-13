import { z } from "zod";
import { TokenSchema } from "@/lib/schemas";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/** RFC 7807 problem body, as returned by every backend error. */
export const ProblemSchema = z.object({
  type: z.string(),
  title: z.string(),
  status: z.number(),
  detail: z.string(),
  instance: z.string().optional(),
  // Present on 422s: which fields failed, e.g. loc = ["body", "email"].
  errors: z
    .array(z.object({ loc: z.array(z.union([z.string(), z.number()])), msg: z.string() }))
    .optional(),
});
export type Problem = z.infer<typeof ProblemSchema>;

export class ApiError extends Error {
  constructor(public readonly problem: Problem) {
    super(problem.detail);
  }
  get status(): number {
    return this.problem.status;
  }
}

// ---- Access token: kept in memory only ----------------------------------------------------
//
// Not in localStorage: any XSS bug could read it from there. In memory it's lost on page
// reload, which is fine: on load we call /auth/refresh, and the browser attaches the
// httpOnly refresh cookie automatically. JavaScript never sees the refresh token at all.

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function hasAccessToken(): boolean {
  return accessToken !== null;
}

// Single-flight: every caller that needs a refresh at the same moment awaits the SAME
// request. Refresh tokens rotate (single use), so two parallel refreshes would present
// the same token twice, and the backend would treat that as theft and log us out.
// (React Strict Mode runs effects twice in dev, so this happens more often than you'd think.)
let refreshing: Promise<string | null> | null = null;

export function refreshSession(): Promise<string | null> {
  refreshing ??= (async () => {
    try {
      const token = await request("/auth/refresh", TokenSchema, { method: "POST" });
      accessToken = token.access_token;
      return accessToken;
    } catch {
      accessToken = null;
      return null;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

// ---- Fetch wrapper ------------------------------------------------------------------------

async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  // JSON bodies only. For FormData (file uploads) the browser must set the multipart
  // Content-Type itself, because it includes the generated boundary string.
  if (typeof init?.body === "string") headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include", // lets the browser send/receive the refresh cookie
  });
  const body: unknown = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    const parsed = ProblemSchema.safeParse(body);
    throw new ApiError(
      parsed.success
        ? parsed.data
        : { type: "about:blank", title: "Error", status: res.status, detail: res.statusText },
    );
  }
  return schema.parse(body);
}

/**
 * Typed API call: validates the response with a Zod schema. If the access token has
 * expired (401), refreshes once and retries, so a 15-minute token expiry is invisible
 * to the user.
 */
export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  try {
    return await request(path, schema, init);
  } catch (err) {
    const isAuthRoute = path.startsWith("/auth/");
    if (!(err instanceof ApiError) || err.status !== 401 || isAuthRoute) throw err;
    if ((await refreshSession()) === null) throw err;
    return request(path, schema, init);
  }
}

/** Map a 422 problem to {fieldName: message} for showing errors next to inputs. */
export function fieldErrors(err: unknown): Record<string, string> {
  if (!(err instanceof ApiError) || !err.problem.errors) return {};
  return Object.fromEntries(
    err.problem.errors.map((e) => [String(e.loc[e.loc.length - 1]), e.msg] as const),
  );
}
