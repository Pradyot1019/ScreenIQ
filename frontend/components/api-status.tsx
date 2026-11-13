"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { HealthSchema } from "@/lib/schemas";

export function ApiStatus() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiFetch("/health", HealthSchema),
  });

  const [label, color] = isPending
    ? ["Checking API…", "bg-yellow-400"]
    : isError
      ? ["API unreachable", "bg-red-500"]
      : [`API ${data.status}`, "bg-emerald-500"];

  return (
    <p role="status" className="inline-flex items-center gap-2 text-sm text-slate-600">
      <span aria-hidden className={`h-2.5 w-2.5 rounded-full ${color}`} />
      {label}
    </p>
  );
}
