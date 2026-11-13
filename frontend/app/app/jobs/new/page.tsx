"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { FormField } from "@/components/auth/form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fieldErrors } from "@/lib/api-client";
import { parseForm } from "@/lib/form";
import { useCreateJob } from "@/lib/jobs";
import { EMPLOYMENT_LABELS, JobInput } from "@/lib/schemas";

export default function NewJobPage() {
  const router = useRouter();
  const create = useCreateJob();
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data, errors } = parseForm(JobInput, e.currentTarget);
    setErrors(errors ?? {});
    if (!data) return;
    try {
      const job = await create.mutateAsync(data);
      router.push(`/app/jobs/${job.id}`); // next: generate the rubric there
    } catch (err) {
      setErrors(fieldErrors(err));
    }
  }

  return (
    <Card className="max-w-3xl">
      <CardHeader>
        <CardTitle>New job</CardTitle>
      </CardHeader>
      <form onSubmit={onSubmit} noValidate>
        <CardContent className="grid gap-4">
          {create.error && !Object.keys(errors).length && (
            <Alert variant="destructive">
              <AlertDescription>{create.error.message}</AlertDescription>
            </Alert>
          )}
          <FormField name="title" label="Job title" error={errors.title} required />
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField name="department" label="Department" error={errors.department} />
            <FormField name="location" label="Location" error={errors.location} />
            <div className="grid gap-2">
              <Label htmlFor="employment_type">Type</Label>
              <select
                id="employment_type"
                name="employment_type"
                defaultValue="full_time"
                className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
              >
                {Object.entries(EMPLOYMENT_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="description">Job description</Label>
            <Textarea
              id="description"
              name="description"
              rows={14}
              placeholder="Paste the full job description. The AI drafts the scoring rubric from it."
              aria-invalid={errors.description ? true : undefined}
              aria-describedby={errors.description ? "description-error" : undefined}
            />
            {errors.description && (
              <p id="description-error" className="text-sm text-destructive">
                {errors.description}
              </p>
            )}
          </div>
        </CardContent>
        <CardFooter className="mt-6">
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create job"}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
