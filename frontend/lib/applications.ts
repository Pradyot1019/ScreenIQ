"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "@/lib/api-client";
import { ApplicationDetailSchema, ApplicationRowSchema } from "@/lib/schemas";

const ACTIVE = new Set(["queued", "running"]);
const POLL_MS = 2000;

export function useApplications(jobId: string) {
  return useQuery({
    queryKey: ["applications", jobId],
    queryFn: () => apiFetch(`/jobs/${jobId}/applications`, z.array(ApplicationRowSchema)),
    // Keep refreshing while any screening is still in progress.
    refetchInterval: (q) =>
      q.state.data?.some((a) => a.screening && ACTIVE.has(a.screening.status)) ? POLL_MS : false,
  });
}

export function useApplication(id: string) {
  return useQuery({
    queryKey: ["application", id],
    queryFn: () => apiFetch(`/applications/${id}`, ApplicationDetailSchema),
    refetchInterval: (q) =>
      q.state.data?.screening && ACTIVE.has(q.state.data.screening.status) ? POLL_MS : false,
  });
}

export function useRescreen(applicationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch(`/applications/${applicationId}/screenings`, z.unknown(), { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["application", applicationId] }),
  });
}

export function useScreenPending(jobId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch(`/jobs/${jobId}/screenings`, z.object({ queued: z.number() }), { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", jobId] }),
  });
}
