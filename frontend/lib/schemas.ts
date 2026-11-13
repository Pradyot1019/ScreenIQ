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

// ---- Jobs & rubric (mirrors backend/app/schemas/jobs.py) --------------------------------

export const JobStatusSchema = z.enum(["draft", "open", "closed"]);
export type JobStatus = z.infer<typeof JobStatusSchema>;

export const EmploymentTypeSchema = z.enum(["full_time", "part_time", "contract", "internship"]);
export type EmploymentType = z.infer<typeof EmploymentTypeSchema>;

export const CriterionTypeSchema = z.enum(["skill", "experience", "education", "other"]);
export type CriterionType = z.infer<typeof CriterionTypeSchema>;

export const CriterionSchema = z.object({
  name: z.string(),
  description: z.string(),
  type: CriterionTypeSchema,
  weight: z.number().int(),
  is_knockout: z.boolean(),
});
export type Criterion = z.infer<typeof CriterionSchema>;

export const JobSchema = z.object({
  id: z.uuid(),
  title: z.string(),
  department: z.string().nullable(),
  location: z.string().nullable(),
  employment_type: EmploymentTypeSchema,
  description: z.string(),
  status: JobStatusSchema,
  slug: z.string(),
  blind_mode: z.boolean(),
  created_by: z.uuid().nullable(),
  created_at: z.string(),
  criteria: z.array(CriterionSchema.extend({ id: z.uuid() })),
});
export type Job = z.infer<typeof JobSchema>;

export const JobPageSchema = z.object({
  items: z.array(
    z.object({
      id: z.uuid(),
      title: z.string(),
      department: z.string().nullable(),
      location: z.string().nullable(),
      employment_type: EmploymentTypeSchema,
      status: JobStatusSchema,
      slug: z.string(),
      created_at: z.string(),
      criteria_count: z.number(),
    }),
  ),
  next_cursor: z.string().nullable(),
});
export type JobPage = z.infer<typeof JobPageSchema>;

export const RubricDraftSchema = z.object({
  criteria: z.array(CriterionSchema),
  prompt_version: z.string(),
});

const optionalText = z
  .string()
  .trim()
  .max(120, "Too long")
  .transform((v) => (v === "" ? null : v));

export const JobInput = z.object({
  title: z.string().trim().min(1, "Required").max(200, "Too long"),
  department: optionalText,
  location: optionalText,
  employment_type: EmploymentTypeSchema,
  description: z
    .string()
    .trim()
    .min(50, "Paste the full job description (at least 50 characters)")
    .max(20000, "Too long (max 20,000 characters)"),
});
export type JobInput = z.infer<typeof JobInput>;

export const EMPLOYMENT_LABELS: Record<EmploymentType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  internship: "Internship",
};
