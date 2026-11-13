"use client";

import Link from "next/link";
import { useState } from "react";
import { KnockoutBadge, RecommendationBadge, ScoreBar } from "@/components/screening/badges";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useApplications, useScreenPending } from "@/lib/applications";

export function CandidatesTable({ jobId, canWrite }: { jobId: string; canWrite: boolean }) {
  const apps = useApplications(jobId);
  const screenPending = useScreenPending(jobId);
  const [minScore, setMinScore] = useState(0);
  const [hideKnockouts, setHideKnockouts] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id].slice(-4)));

  const rows = (apps.data ?? []).filter((a) => {
    const s = a.screening;
    if (minScore && (s?.overall_score ?? -1) < minScore) return false;
    if (hideKnockouts && s?.knockout_failed) return false;
    return true;
  });
  const pending = (apps.data ?? []).filter(
    (a) => !a.screening || a.screening.status === "failed",
  ).length;

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-4">
        <h2 className="mr-auto text-lg font-semibold">
          Candidates{apps.data ? ` (${apps.data.length})` : ""}
        </h2>
        <label className="flex items-center gap-2 text-sm">
          Min score
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
          >
            <option value={0}>Any</option>
            <option value={50}>50+</option>
            <option value={75}>75+</option>
          </select>
        </label>
        <div className="flex items-center gap-2">
          <Checkbox
            id="hide-ko"
            checked={hideKnockouts}
            onCheckedChange={(v) => setHideKnockouts(v === true)}
          />
          <Label htmlFor="hide-ko">Hide must-have missing</Label>
        </div>
        <Button
          asChild={selected.length >= 2}
          variant="outline"
          disabled={selected.length < 2}
          title={selected.length < 2 ? "Tick 2 to 4 candidates to compare" : undefined}
        >
          {selected.length >= 2 ? (
            <Link href={`/app/jobs/${jobId}/compare?ids=${selected.join(",")}`}>
              Compare {selected.length}
            </Link>
          ) : (
            <span>Compare</span>
          )}
        </Button>
        {canWrite && pending > 0 && (
          <Button
            variant="outline"
            onClick={() => screenPending.mutate()}
            disabled={screenPending.isPending}
          >
            Screen {pending} pending
          </Button>
        )}
      </div>

      {screenPending.error && (
        <Alert variant="destructive">
          <AlertDescription>{screenPending.error.message}</AlertDescription>
        </Alert>
      )}

      {apps.isPending ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : !apps.data?.length ? (
        <p className="text-sm text-muted-foreground">
          No candidates yet. Upload resumes to get started.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8">
                <span className="sr-only">Select to compare</span>
              </TableHead>
              <TableHead>Candidate</TableHead>
              <TableHead>Experience</TableHead>
              <TableHead>Score</TableHead>
              <TableHead>AI assessment</TableHead>
              <TableHead>Stage</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((a) => {
              const s = a.screening;
              return (
                <TableRow key={a.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`Select ${a.candidate.full_name ?? "candidate"} to compare`}
                      checked={selected.includes(a.id)}
                      onCheckedChange={() => toggle(a.id)}
                    />
                  </TableCell>
                  <TableCell>
                    <Link href={`/app/applications/${a.id}`} className="font-medium hover:underline">
                      {a.candidate.full_name ?? "Unnamed candidate"}
                    </Link>
                    <div className="text-xs text-muted-foreground">{a.candidate.email}</div>
                  </TableCell>
                  <TableCell>
                    {a.candidate.total_experience_years != null
                      ? `${a.candidate.total_experience_years} yrs`
                      : "—"}
                  </TableCell>
                  <TableCell>
                    {s?.status === "done" && s.overall_score != null ? (
                      <ScoreBar score={s.overall_score} />
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        {!s ? "Not screened" : s.status === "failed" ? "Failed" : "Screening…"}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {s?.recommendation && <RecommendationBadge value={s.recommendation} />}
                      {s?.knockout_failed && <KnockoutBadge />}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">
                      {a.stage}
                    </Badge>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
      <p className="text-xs text-muted-foreground">
        AI scores are a starting point, not a decision. Every score links to the resume evidence
        behind it, and only people move candidates between stages.
      </p>
    </div>
  );
}
