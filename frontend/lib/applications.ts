"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "@/lib/api-client";
import {
  ApplicationDetailSchema,
  ApplicationRowSchema,
  CompareSchema,
  NoteSchema,
  ResumeViewSchema,
  type ApplicationRow,
  type Stage,
} from "@/lib/schemas";

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

// ---- Phase 5: stages, notes, resume view, compare --------------------------------------

/** Move a candidate. Optimistic: the card moves instantly, and snaps back on error. */
export function useMoveStage(jobId: string) {
  const qc = useQueryClient();
  const key = ["applications", jobId];
  return useMutation({
    mutationFn: ({ id, stage }: { id: string; stage: Stage }) =>
      apiFetch(`/applications/${id}`, ApplicationRowSchema, {
        method: "PATCH",
        body: JSON.stringify({ stage }),
      }),
    onMutate: async ({ id, stage }) => {
      await qc.cancelQueries({ queryKey: key });
      const previous = qc.getQueryData<ApplicationRow[]>(key);
      qc.setQueryData<ApplicationRow[]>(key, (rows) =>
        rows?.map((r) => (r.id === id ? { ...r, stage } : r)),
      );
      return { previous };
    },
    onError: (_err, _vars, context) => qc.setQueryData(key, context?.previous),
    onSettled: (_data, _err, { id }) => {
      void qc.invalidateQueries({ queryKey: key });
      void qc.invalidateQueries({ queryKey: ["application", id] });
    },
  });
}

export function useNotes(applicationId: string) {
  return useQuery({
    queryKey: ["notes", applicationId],
    queryFn: () => apiFetch(`/applications/${applicationId}/notes`, z.array(NoteSchema)),
  });
}

export function useAddNote(applicationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: string) =>
      apiFetch(`/applications/${applicationId}/notes`, NoteSchema, {
        method: "POST",
        body: JSON.stringify({ body }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes", applicationId] }),
  });
}

export function useResume(applicationId: string, screeningId: string | undefined) {
  return useQuery({
    // Re-fetch when the screening changes: highlights come from the latest screening.
    queryKey: ["resume", applicationId, screeningId],
    queryFn: () => apiFetch(`/applications/${applicationId}/resume`, ResumeViewSchema),
    staleTime: 4 * 60_000, // the signed URL lives 5 minutes
  });
}

export function useCompare(jobId: string, ids: string[]) {
  return useQuery({
    queryKey: ["compare", jobId, ids],
    queryFn: () =>
      apiFetch(
        `/jobs/${jobId}/applications:compare?ids=${ids.map(encodeURIComponent).join(",")}`,
        CompareSchema,
      ),
    enabled: ids.length >= 2,
  });
}
