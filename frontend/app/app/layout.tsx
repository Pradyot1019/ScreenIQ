"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useLogout, useMe } from "@/lib/auth";

/**
 * Guard for everything under /app.
 *
 * This is a UX guard, not the security boundary. The API rejects any request without a
 * valid token no matter what the browser shows; this just avoids flashing a half-empty
 * page and sends logged-out visitors to /login (and back here afterwards).
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const me = useMe();
  const logout = useLogout();

  const loggedOut = me.isSuccess && me.data === null;
  useEffect(() => {
    if (loggedOut) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loggedOut, pathname, router]);

  if (me.isError) {
    return (
      <p role="alert" className="p-8 text-sm text-destructive">
        Couldn&apos;t reach the API. Is the backend running?
      </p>
    );
  }
  if (!me.data) {
    return (
      <p role="status" className="p-8 text-sm text-muted-foreground">
        Loading…
      </p>
    );
  }

  const active = me.data.memberships.find((m) => m.org_id === me.data?.active_org_id);

  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-3">
          <Link href="/app" className="font-semibold tracking-tight">
            ScreenIQ
          </Link>
          {active && <span className="text-sm text-muted-foreground">{active.org_name}</span>}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{me.data.user.full_name}</span>
          <Button
            variant="outline"
            size="sm"
            disabled={logout.isPending}
            onClick={() => logout.mutate(undefined, { onSettled: () => router.replace("/login") })}
          >
            Log out
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}
