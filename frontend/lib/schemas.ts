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

// ---- Resume intake (mirrors backend/app/schemas/intake.py) ------------------------------

export const ParseStatusSchema = z.enum(["queued", "parsing", "parsed", "failed"]);
export type ParseStatus = z.infer<typeof ParseStatusSchema>;

export const BatchSchema = z.object({
  id: z.uuid(),
  job_id: z.uuid(),
  status: z.enum(["processing", "done"]),
  total: z.number(),
  processed: z.number(),
  failed: z.number(),
  created_at: z.string(),
  files: z.array(
    z.object({
      resume_id: z.uuid(),
      filename: z.string(),
      status: ParseStatusSchema,
      error: z.string().nullable(),
      candidate_id: z.uuid().nullable(),
      candidate_name: z.string().nullable(),
    }),
  ),
});
export type Batch = z.infer<typeof BatchSchema>;

// ---- Applications & screenings (mirrors backend/app/schemas/applications.py) ------------

export const StageSchema = z.enum([
  "applied",
  "screened",
  "shortlisted",
  "interview",
  "offer",
  "hired",
  "rejected",
]);
export type Stage = z.infer<typeof StageSchema>;
export const RecommendationSchema = z.enum(["strong", "possible", "weak"]);
export type Recommendation = z.infer<typeof RecommendationSchema>;
export const ScreeningStatusSchema = z.enum(["queued", "running", "done", "failed"]);

// Decimals arrive as strings ("88.00") to keep exact precision; convert for display.
const decimal = z.string().transform(Number);

const CandidateBriefSchema = z.object({
  id: z.uuid(),
  full_name: z.string().nullable(),
  email: z.string().nullable(),
  total_experience_years: decimal.nullable(),
});

const ScreeningBriefSchema = z.object({
  id: z.uuid(),
  status: ScreeningStatusSchema,
  overall_score: decimal.nullable(),
  recommendation: RecommendationSchema.nullable(),
  knockout_failed: z.boolean().nullable(),
});

export const ApplicationRowSchema = z.object({
  id: z.uuid(),
  job_id: z.uuid(),
  stage: StageSchema,
  created_at: z.string(),
  candidate: CandidateBriefSchema,
  screening: ScreeningBriefSchema.nullable(),
});
export type ApplicationRow = z.infer<typeof ApplicationRowSchema>;

export const ApplicationDetailSchema = z.object({
  id: z.uuid(),
  job_id: z.uuid(),
  stage: StageSchema,
  created_at: z.string(),
  candidate: CandidateBriefSchema,
  profile: z.object({
    phone: z.string().nullable().optional(),
    links: z.array(z.string()).default([]),
    skills: z.array(z.string()).default([]),
    experience: z
      .array(
        z.object({
          company: z.string().nullable(),
          role: z.string().nullable(),
          start: z.string().nullable(),
          end: z.string().nullable(),
        }),
      )
      .default([]),
    education: z
      .array(
        z.object({
          institution: z.string().nullable(),
          degree: z.string().nullable(),
          field: z.string().nullable(),
        }),
      )
      .default([]),
  }),
  screening: ScreeningBriefSchema.extend({
    summary: z.string().nullable(),
    strengths: z.array(z.string()),
    gaps: z.array(z.string()),
    model: z.string().nullable(),
    prompt_version: z.string().nullable(),
    error: z.string().nullable(),
    created_at: z.string(),
    criterion_scores: z.array(
      z.object({
        criterion_name: z.string(),
        weight: z.number(),
        is_knockout: z.boolean(),
        score: z.number(),
        reasoning: z.string(),
        evidence: z.array(z.string()),
        rejected_evidence: z.array(z.string()),
        low_confidence: z.boolean(),
      }),
    ),
  }).nullable(),
  history: z.array(
    z.object({
      from_stage: StageSchema,
      to_stage: StageSchema,
      actor_name: z.string().nullable(),
      created_at: z.string(),
    }),
  ),
});
export type ApplicationDetail = z.infer<typeof ApplicationDetailSchema>;

export const STAGES = StageSchema.options;
export const STAGE_LABELS: Record<Stage, string> = {
  applied: "Applied",
  screened: "Screened",
  shortlisted: "Shortlisted",
  interview: "Interview",
  offer: "Offer",
  hired: "Hired",
  rejected: "Rejected",
};

export const NoteSchema = z.object({
  id: z.uuid(),
  body: z.string(),
  author_name: z.string().nullable(),
  created_at: z.string(),
});
export type Note = z.infer<typeof NoteSchema>;

export const ResumeViewSchema = z.object({
  filename: z.string(),
  mime_type: z.string(),
  url: z.string().nullable(),
  url_expires_in: z.number(),
  text: z.string(),
  highlights: z.array(z.object({ start: z.number(), end: z.number(), criterion: z.string() })),
});
export type ResumeView = z.infer<typeof ResumeViewSchema>;

export const CompareSchema = z.object({
  criteria: z.array(z.string()),
  candidates: z.array(
    z.object({
      application_id: z.uuid(),
      name: z.string().nullable(),
      stage: StageSchema,
      overall_score: decimal.nullable(),
      recommendation: RecommendationSchema.nullable(),
      knockout_failed: z.boolean().nullable(),
      scores: z.record(z.string(), z.number()),
      low_confidence: z.array(z.string()),
    }),
  ),
});
export type Compare = z.infer<typeof CompareSchema>;
