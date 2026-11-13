import type { z } from "zod";

/**
 * Validate a submitted <form> with a Zod schema.
 * Returns the typed data, or a {field: message} map to show next to the inputs.
 */
export function parseForm<S extends z.ZodType<Record<string, unknown>>>(
  schema: S,
  form: HTMLFormElement,
): { data: z.infer<S>; errors: null } | { data: null; errors: Record<string, string> } {
  const result = schema.safeParse(Object.fromEntries(new FormData(form)));
  if (result.success) return { data: result.data, errors: null };
  const errors: Record<string, string> = {};
  for (const issue of result.error.issues) {
    const key = String(issue.path[0]);
    errors[key] ??= issue.message;
  }
  return { data: null, errors };
}
