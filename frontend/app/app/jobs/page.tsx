"use client";

import Link from "next/link";
import { StatusBadge } from "@/components/jobs/status-badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCanWrite } from "@/lib/auth";
import { useJobs } from "@/lib/jobs";
import { EMPLOYMENT_LABELS } from "@/lib/schemas";

export default function JobsPage() {
  const jobs = useJobs();
  const canWrite = useCanWrite();
  const items = jobs.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="grid gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
        {canWrite && (
          <Button asChild>
            <Link href="/app/jobs/new">New job</Link>
          </Button>
        )}
      </div>

      {jobs.isPending ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : jobs.isError ? (
        <p role="alert" className="text-sm text-destructive">
          Couldn&apos;t load jobs.
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No jobs yet.{canWrite && " Create one to draft a scoring rubric from its description."}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Rubric</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((job) => (
              <TableRow key={job.id}>
                <TableCell className="font-medium">
                  <Link href={`/app/jobs/${job.id}`} className="hover:underline">
                    {job.title}
                  </Link>
                  {job.department && (
                    <span className="ml-2 text-muted-foreground">{job.department}</span>
                  )}
                </TableCell>
                <TableCell>{EMPLOYMENT_LABELS[job.employment_type]}</TableCell>
                <TableCell>{job.location ?? "—"}</TableCell>
                <TableCell>
                  {job.criteria_count ? `${job.criteria_count} criteria` : "Not set"}
                </TableCell>
                <TableCell>
                  <StatusBadge status={job.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {jobs.hasNextPage && (
        <Button
          variant="outline"
          className="justify-self-center"
          disabled={jobs.isFetchingNextPage}
          onClick={() => jobs.fetchNextPage()}
        >
          {jobs.isFetchingNextPage ? "Loading…" : "Load more"}
        </Button>
      )}
    </div>
  );
}
