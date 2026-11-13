"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import {
  apiFetch,
  hasAccessToken,
  refreshSession,
  setAccessToken,
} from "@/lib/api-client";
import { MeSchema, TokenSchema, type LoginInput, type Me, type SignupInput } from "@/lib/schemas";

export const ME_KEY = ["me"] as const;

/**
 * The current user, or null if not logged in. On a fresh page load there's no access
 * token in memory yet, so we first try a silent refresh using the httpOnly cookie.
 */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async (): Promise<Me | null> => {
      if (!hasAccessToken() && (await refreshSession()) === null) return null;
      return apiFetch("/me", MeSchema);
    },
    retry: false,
    staleTime: 5 * 60_000,
  });
}

function useAuthMutation<TInput>(path: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: TInput) => {
      const token = await apiFetch(path, TokenSchema, {
        method: "POST",
        body: JSON.stringify(input),
      });
      setAccessToken(token.access_token);
    },
    // Drop any cached "not logged in" answer so useMe refetches with the new token.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_KEY }),
  });
}

export const useLogin = () => useAuthMutation<LoginInput>("/auth/login");
export const useSignup = () => useAuthMutation<SignupInput>("/auth/signup");

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch("/auth/logout", z.null(), { method: "POST" }),
    onSettled: () => {
      // Even if the request failed, forget everything locally.
      setAccessToken(null);
      queryClient.clear();
    },
  });
}

/**
 * Only allow same-site relative paths after login (prevents open redirects).
 * "/app/jobs" is fine; "//evil.com" and "/\evil.com" are treated by browsers as
 * another site, so they're rejected.
 */
export function safeNextPath(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) {
    return "/app";
  }
  return next;
}

/** Owners and recruiters can edit jobs; viewers (hiring managers) can only read. */
export function useCanWrite(): boolean {
  const { data } = useMe();
  const role = data?.memberships.find((m) => m.org_id === data.active_org_id)?.role;
  return role === "owner" || role === "recruiter";
}
