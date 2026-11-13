import { ApiStatus } from "@/components/api-status";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6">
      <h1 className="text-4xl font-semibold tracking-tight text-slate-900">ScreenIQ</h1>
      <p className="text-lg text-slate-700">
        Explainable, evidence-backed resume screening. Every score cites the resume, and a human
        always makes the final call.
      </p>
      <ApiStatus />
    </main>
  );
}
