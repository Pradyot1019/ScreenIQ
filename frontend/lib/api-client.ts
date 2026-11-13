import { z } from "zod";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/** RFC 7807 problem body, as returned by every backend error. */
export const ProblemSchema = z.object({
  type: z.string(),
  title: z.string(),
  status: z.number(),
  detail: z.string(),
  instance: z.string().optional(),
});
export type Problem = z.infer<typeof ProblemSchema>;

export class ApiError extends Error {
  constructor(public readonly problem: Problem) {
    super(problem.detail);
  }
}

/**
 * Typed fetch wrapper: every response is validated with a Zod schema, so a
 * backend contract change fails loudly here instead of deep inside a component.
 */
export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include", // sends the httpOnly refresh cookie (Phase 1)
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body: unknown = res.status === 204 ? null : await res.json();
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
