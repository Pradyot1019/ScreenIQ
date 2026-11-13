"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
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
import { ApiError, fieldErrors } from "@/lib/api-client";
import { useSignup } from "@/lib/auth";
import { parseForm } from "@/lib/form";
import { SignupInput } from "@/lib/schemas";

export default function SignupPage() {
  const router = useRouter();
  const signup = useSignup();
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data, errors } = parseForm(SignupInput, e.currentTarget);
    setErrors(errors ?? {});
    if (!data) return;
    try {
      await signup.mutateAsync(data);
      router.replace("/app");
    } catch (err) {
      // The client checks match the server's, but the server is the authority:
      // if it still returns 422, show its messages next to the right fields.
      setErrors(fieldErrors(err));
    }
  }

  const error = signup.error;
  const serverError =
    error instanceof ApiError && error.status !== 422
      ? error.message
      : error && !(error instanceof ApiError)
        ? "Something went wrong."
        : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create your workspace</CardTitle>
        <CardDescription>You&apos;ll be the owner of a new organization.</CardDescription>
      </CardHeader>
      <form onSubmit={onSubmit} noValidate>
        <CardContent className="grid gap-4">
          {serverError && (
            <Alert variant="destructive">
              <AlertDescription>{serverError}</AlertDescription>
            </Alert>
          )}
          <FormField
            name="full_name"
            label="Your name"
            autoComplete="name"
            error={errors.full_name}
            required
          />
          <FormField
            name="email"
            label="Work email"
            type="email"
            autoComplete="email"
            error={errors.email}
            required
          />
          <FormField
            name="password"
            label="Password"
            type="password"
            autoComplete="new-password"
            error={errors.password}
            minLength={8}
            required
          />
          <FormField
            name="org_name"
            label="Organization name"
            autoComplete="organization"
            error={errors.org_name}
            required
          />
        </CardContent>
        <CardFooter className="mt-6 flex flex-col gap-3">
          <Button type="submit" className="w-full" disabled={signup.isPending}>
            {signup.isPending ? "Creating…" : "Create account"}
          </Button>
          <p className="text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="text-foreground underline underline-offset-4">
              Log in
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
