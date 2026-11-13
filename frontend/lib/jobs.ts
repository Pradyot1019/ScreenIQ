"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "@/lib/api-client";
import {
  JobPageSchema,
  JobSchema,
  RubricDraftSchema,
  type Criterion,
  type Job,
  type JobInput,
} from "@/lib/schemas";

const JOBS_KEY = ["jobs"] as const;
const jobKey = (id: string) => ["jobs", id] as const;

export function useJobs() {
  return useInfiniteQuery({
    queryKey: JOBS_KEY,
    queryFn: ({ pageParam }) =>
      apiFetch(`/jobs?limit=20${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`, JobPageSchema),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
}

export function useJob(id: string) {
  return useQuery({ queryKey: jobKey(id), queryFn: () => apiFetch(`/jobs/${id}`, JobSchema) });
}

/** After any job write: put the fresh job in the cache and refresh the list. */
function useJobMutation<TInput>(request: (input: TInput) => Promise<Job>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: (job) => {
      qc.setQueryData(jobKey(job.id), job);
      return qc.invalidateQueries({ queryKey: JOBS_KEY, exact: true });
    },
  });
}

const post = (path: string, body?: unknown, method = "POST") =>
  apiFetch(path, JobSchema, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export const useCreateJob = () => useJobMutation((input: JobInput) => post("/jobs", input));
export const useSaveRubric = (id: string) =>
  useJobMutation((criteria: Criterion[]) => post(`/jobs/${id}/rubric`, { criteria }, "PUT"));
export const usePublishJob = (id: string) => useJobMutation(() => post(`/jobs/${id}/publish`));
export const useCloseJob = (id: string) => useJobMutation(() => post(`/jobs/${id}/close`));

export function useDeleteJob(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch(`/jobs/${id}`, z.null(), { method: "DELETE" }),
    onSuccess: () => {
      qc.removeQueries({ queryKey: jobKey(id) });
      return qc.invalidateQueries({ queryKey: JOBS_KEY, exact: true });
    },
  });
}

/** AI draft: returns suggested criteria; nothing is saved until useSaveRubric. */
export function useGenerateRubric(id: string) {
  return useMutation({
    mutationFn: () => apiFetch(`/jobs/${id}/rubric:generate`, RubricDraftSchema, { method: "POST" }),
  });
}
