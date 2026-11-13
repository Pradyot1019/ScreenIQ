import Link from "next/link";
import { ApiStatus } from "@/components/api-status";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6">
      <h1 className="text-4xl font-semibold tracking-tight">ScreenIQ</h1>
      <p className="text-lg text-muted-foreground">
        Explainable, evidence-backed resume screening. Every score cites the resume, and a human
        always makes the final call.
      </p>
      <div className="flex gap-3">
        <Button asChild>
          <Link href="/signup">Get started</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/login">Log in</Link>
        </Button>
      </div>
      <ApiStatus />
    </main>
  );
}
