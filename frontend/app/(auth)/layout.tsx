import Link from "next/link";

// "(auth)" is a route group: it shares this layout without adding "/auth" to the URL,
// so the pages live at /login and /signup.
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-muted/40 px-4 py-12">
      <Link href="/" className="text-xl font-semibold tracking-tight">
        ScreenIQ
      </Link>
      <div className="w-full max-w-sm">{children}</div>
    </main>
  );
}
