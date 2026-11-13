"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { KnockoutBadge, RecommendationBadge, ScoreBar } from "@/components/screening/badges";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useApplication, useRescreen } from "@/lib/applications";
import { useCanWrite } from "@/lib/auth";

export default function ApplicationPage() {
  const { id } = useParams<{ id: string }>();
  const app = useApplication(id);
  const rescreen = useRescreen(id);
  const canWrite = useCanWrite();

  if (app.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (app.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {app.error.message}
      </p>
    );
  }

  const { candidate, profile, screening: s } = app.data;
  const busy = s && (s.status === "queued" || s.status === "running");

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid gap-1">
          <Link href={`/app/jobs/${app.data.job_id}`} className="text-sm text-muted-foreground hover:underline">
            ← Back to job
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight">
            {candidate.full_name ?? "Unnamed candidate"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {[candidate.email, profile.phone, candidate.total_experience_years != null && `${candidate.total_experience_years} yrs experience`]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="capitalize">
            {app.data.stage}
          </Badge>
          {canWrite && (
            <Button
              variant="outline"
              onClick={() => rescreen.mutate()}
              disabled={rescreen.isPending || !!busy}
            >
              <RefreshCw />
              {s ? "Re-screen" : "Screen"}
            </Button>
          )}
        </div>
      </div>

      {rescreen.error && (
        <Alert variant="destructive">
          <AlertDescription>{rescreen.error.message}</AlertDescription>
        </Alert>
      )}

      {!s ? (
        <p className="text-sm text-muted-foreground">Not screened yet.</p>
      ) : busy ? (
        <p role="status" className="text-sm text-muted-foreground">
          Screening in progress…
        </p>
      ) : s.status === "failed" ? (
        <Alert variant="destructive">
          <AlertDescription>Screening failed: {s.error}</AlertDescription>
        </Alert>
      ) : (
        <>
          <Card>
            <CardContent className="grid gap-3 pt-6">
              <div className="flex flex-wrap items-center gap-3">
                {s.overall_score != null && <ScoreBar score={s.overall_score} />}
                {s.recommendation && <RecommendationBadge value={s.recommendation} />}
                {s.knockout_failed && <KnockoutBadge />}
              </div>
              {s.summary && <p className="text-sm">{s.summary}</p>}
              <div className="grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <h3 className="mb-1 font-medium">Strengths</h3>
                  <ul className="list-disc pl-5 text-muted-foreground">
                    {s.strengths.map((x) => <li key={x}>{x}</li>)}
                  </ul>
                </div>
                <div>
                  <h3 className="mb-1 font-medium">Gaps</h3>
                  <ul className="list-disc pl-5 text-muted-foreground">
                    {s.gaps.map((x) => <li key={x}>{x}</li>)}
                  </ul>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                {s.model} · {s.prompt_version} · {new Date(s.created_at).toLocaleString()}
              </p>
            </CardContent>
          </Card>

          <div className="grid gap-3">
            <h2 className="text-lg font-semibold">Why this score</h2>
            {s.criterion_scores.map((c) => (
              <Card key={c.criterion_name}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex flex-wrap items-center gap-2 text-base">
                    {c.criterion_name}
                    <span className="text-sm font-normal text-muted-foreground">
                      weight {c.weight}
                    </span>
                    {c.is_knockout && <Badge variant="outline">Must-have</Badge>}
                    {c.low_confidence && (
                      <Badge variant="secondary" title="Some cited evidence couldn't be found in the resume">
                        <AlertTriangle /> Low confidence
                      </Badge>
                    )}
                    <span className="ml-auto tabular-nums">{c.score}/10</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid gap-2 text-sm">
                  <p className="text-muted-foreground">{c.reasoning}</p>
                  {c.evidence.map((q) => (
                    <blockquote key={q} className="border-l-2 border-primary pl-3 italic">
                      “{q}”
                    </blockquote>
                  ))}
                  {c.rejected_evidence.map((q) => (
                    <p key={q} className="text-xs text-muted-foreground">
                      <span className="line-through">“{q}”</span> not found in the resume, so
                      it was ignored
                    </p>
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Profile</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm">
          {profile.experience.length > 0 && (
            <div>
              <h3 className="mb-1 font-medium">Experience</h3>
              <ul className="grid gap-1 text-muted-foreground">
                {profile.experience.map((e, i) => (
                  <li key={i}>
                    {e.role} · {e.company}{" "}
                    <span className="text-xs">({e.start ?? "?"} – {e.end ?? "?"})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {profile.education.length > 0 && (
            <div>
              <h3 className="mb-1 font-medium">Education</h3>
              <ul className="text-muted-foreground">
                {profile.education.map((e, i) => (
                  <li key={i}>{[e.degree, e.field, e.institution].filter(Boolean).join(", ")}</li>
                ))}
              </ul>
            </div>
          )}
          {profile.skills.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {profile.skills.map((sk) => (
                <Badge key={sk} variant="secondary">
                  {sk}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
