"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { RubricEditor } from "@/components/jobs/rubric-editor";
import { StatusBadge } from "@/components/jobs/status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useCanWrite } from "@/lib/auth";
import { useCloseJob, useDeleteJob, useJob, usePublishJob } from "@/lib/jobs";
import { EMPLOYMENT_LABELS } from "@/lib/schemas";

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const job = useJob(id);
  const canWrite = useCanWrite();
  const publish = usePublishJob(id);
  const close = useCloseJob(id);
  const remove = useDeleteJob(id);

  if (job.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (job.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {job.error.message} <Link href="/app/jobs" className="underline">Back to jobs</Link>
      </p>
    );
  }

  const j = job.data;
  const actionError = publish.error ?? close.error ?? remove.error;

  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid gap-1">
          <Link href="/app/jobs" className="text-sm text-muted-foreground hover:underline">
            ← Jobs
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{j.title}</h1>
            <StatusBadge status={j.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {[j.department, j.location, EMPLOYMENT_LABELS[j.employment_type]]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        {canWrite && (
          <div className="flex gap-2">
            {j.status === "draft" && (
              <Button onClick={() => publish.mutate()} disabled={publish.isPending}>
                Publish
              </Button>
            )}
            {j.status === "open" && (
              <Button variant="outline" onClick={() => close.mutate()} disabled={close.isPending}>
                Close job
              </Button>
            )}
            <Button
              variant="ghost"
              disabled={remove.isPending}
              onClick={async () => {
                if (!confirm(`Delete "${j.title}"? This can't be undone.`)) return;
                await remove.mutateAsync();
                router.replace("/app/jobs");
              }}
            >
              Delete
            </Button>
          </div>
        )}
      </div>

      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError.message}</AlertDescription>
        </Alert>
      )}

      {/* key: re-mount the editor with fresh rows whenever the saved rubric changes */}
      <RubricEditor
        key={j.criteria.map((c) => c.id).join()}
        job={j}
        editable={canWrite && j.status !== "closed"}
      />

      <details className="rounded-lg border p-4">
        <summary className="cursor-pointer text-sm font-medium">Job description</summary>
        <p className="mt-3 text-sm whitespace-pre-wrap text-muted-foreground">{j.description}</p>
      </details>
    </div>
  );
}
