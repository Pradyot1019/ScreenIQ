import { z } from "zod";

// Response schemas mirror backend/app/schemas/*. If the API changes shape, parsing fails
// loudly in api-client.ts instead of rendering `undefined` somewhere deep in the UI.

export const HealthSchema = z.object({ status: z.literal("ok") });
export type Health = z.infer<typeof HealthSchema>;

export const TokenSchema = z.object({
  access_token: z.string(),
  token_type: z.literal("bearer"),
  expires_in: z.number(),
});
export type Token = z.infer<typeof TokenSchema>;

export const RoleSchema = z.enum(["owner", "recruiter", "viewer"]);
export type Role = z.infer<typeof RoleSchema>;

export const MeSchema = z.object({
  user: z.object({
    id: z.uuid(),
    email: z.string(),
    full_name: z.string(),
    email_verified: z.boolean(),
  }),
  active_org_id: z.uuid(),
  memberships: z.array(
    z.object({ org_id: z.uuid(), org_name: z.string(), org_slug: z.string(), role: RoleSchema }),
  ),
});
export type Me = z.infer<typeof MeSchema>;

// ---- Request (form) schemas: same rules as the backend, checked before sending ----------

const name = z.string().trim().min(1, "Required").max(200, "Too long");

export const LoginInput = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Required").max(128),
});
export type LoginInput = z.infer<typeof LoginInput>;

export const SignupInput = z.object({
  full_name: name,
  email: z.email("Enter a valid email"),
  password: z.string().min(8, "At least 8 characters").max(128, "At most 128 characters"),
  org_name: name,
});
export type SignupInput = z.infer<typeof SignupInput>;
