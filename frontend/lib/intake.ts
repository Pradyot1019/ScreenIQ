"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { BatchSchema } from "@/lib/schemas";

export const MAX_FILES = 50;
export const MAX_BYTES = 5 * 1024 * 1024;
export const ACCEPTED = [".pdf", ".docx"];

/** Quick checks before uploading. The server re-checks everything by file content. */
export function precheck(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED.some((ext) => name.endsWith(ext))) return "Only PDF and DOCX files are supported.";
  if (file.size > MAX_BYTES) return "Larger than 5 MB.";
  if (file.size === 0) return "The file is empty.";
  return null;
}

export function useUploadResumes(jobId: string) {
  return useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      return apiFetch(`/jobs/${jobId}/resumes`, BatchSchema, { method: "POST", body: form });
    },
  });
}

/** Polls every 1.5 s until the worker has finished every file. */
export function useBatch(batchId: string | null) {
  return useQuery({
    queryKey: ["batches", batchId],
    queryFn: () => apiFetch(`/batches/${batchId}`, BatchSchema),
    enabled: batchId !== null,
    refetchInterval: (q) => (q.state.data?.status === "done" ? false : 1500),
  });
}
