"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMe } from "@/lib/auth";

export default function DashboardPage() {
  const { data: me } = useMe(); // already loaded by the /app layout, served from cache
  if (!me) return null;
  const active = me.memberships.find((m) => m.org_id === me.active_org_id);

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Welcome, {me.user.full_name.split(" ")[0]}
        </h1>
        <p className="text-sm text-muted-foreground">
          {active?.org_name} · you&apos;re {active?.role === "owner" ? "the" : "a"} {active?.role}
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Jobs</CardTitle>
          <CardDescription>
            Create a job, paste its description, and ScreenIQ drafts a scoring rubric. Coming in
            Phase 2.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">No jobs yet.</CardContent>
      </Card>
    </div>
  );
}
