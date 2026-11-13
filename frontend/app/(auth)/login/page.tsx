"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { FormField } from "@/components/auth/form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/lib/api-client";
import { safeNextPath, useLogin, useMe } from "@/lib/auth";
import { parseForm } from "@/lib/form";
import { LoginInput } from "@/lib/schemas";

function LoginForm() {
  const router = useRouter();
  const next = safeNextPath(useSearchParams().get("next"));
  const me = useMe();
  const login = useLogin();
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Already logged in (e.g. opened /login in a new tab): skip the form.
  useEffect(() => {
    if (me.data) router.replace(next);
  }, [me.data, next, router]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data, errors } = parseForm(LoginInput, e.currentTarget);
    setErrors(errors ?? {});
    if (!data) return;
    try {
      await login.mutateAsync(data);
      router.replace(next);
    } catch {
      // Shown below from login.error.
    }
  }

  const serverError =
    login.error instanceof ApiError ? login.error.message : login.error ? "Something went wrong." : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Log in</CardTitle>
        <CardDescription>Welcome back to ScreenIQ.</CardDescription>
      </CardHeader>
      <form onSubmit={onSubmit} noValidate>
        <CardContent className="grid gap-4">
          {serverError && (
            <Alert variant="destructive">
              <AlertDescription>{serverError}</AlertDescription>
            </Alert>
          )}
          <FormField
            name="email"
            label="Email"
            type="email"
            autoComplete="email"
            error={errors.email}
            required
          />
          <FormField
            name="password"
            label="Password"
            type="password"
            autoComplete="current-password"
            error={errors.password}
            required
          />
        </CardContent>
        <CardFooter className="mt-6 flex flex-col gap-3">
          <Button type="submit" className="w-full" disabled={login.isPending}>
            {login.isPending ? "Logging in…" : "Log in"}
          </Button>
          <p className="text-sm text-muted-foreground">
            No account?{" "}
            <Link href="/signup" className="text-foreground underline underline-offset-4">
              Sign up
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}

export default function LoginPage() {
  // useSearchParams needs a Suspense boundary so Next can prerender the rest of the page.
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
