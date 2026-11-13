"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { KnockoutBadge, RecommendationBadge } from "@/components/screening/badges";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCompare } from "@/lib/applications";
import { STAGE_LABELS } from "@/lib/schemas";

function Comparison() {
  const { id } = useParams<{ id: string }>();
  const ids = (useSearchParams().get("ids") ?? "").split(",").filter(Boolean);
  const cmp = useCompare(id, ids);

  const back = (
    <Link href={`/app/jobs/${id}`} className="text-sm text-muted-foreground hover:underline">
      ← Back to job
    </Link>
  );
  if (ids.length < 2) {
    return (
      <div className="grid gap-2">
        {back}
        <p className="text-sm text-muted-foreground">
          Pick 2 to 4 candidates in the Candidates table to compare them.
        </p>
      </div>
    );
  }
  if (cmp.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (cmp.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {cmp.error.message}
      </p>
    );
  }

  const { criteria, candidates } = cmp.data;
  const best = (criterion: string) =>
    Math.max(...candidates.map((c) => c.scores[criterion] ?? -1));

  return (
    <div className="grid gap-6">
      <div className="grid gap-1">
        {back}
        <h1 className="text-2xl font-semibold tracking-tight">Compare candidates</h1>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-56">Criterion</TableHead>
            {candidates.map((c) => (
              <TableHead key={c.application_id}>
                <Link href={`/app/applications/${c.application_id}`} className="hover:underline">
                  {c.name ?? "Unnamed"}
                </Link>
                <div className="text-xs font-normal">{STAGE_LABELS[c.stage]}</div>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell className="font-medium">Overall (0–100)</TableCell>
            {candidates.map((c) => (
              <TableCell key={c.application_id} className="align-top">
                <div className="grid justify-items-start gap-1">
                  <span className="text-lg font-semibold tabular-nums">
                    {c.overall_score != null ? Math.round(c.overall_score) : "—"}
                  </span>
                  {c.recommendation && <RecommendationBadge value={c.recommendation} />}
                  {c.knockout_failed && <KnockoutBadge />}
                </div>
              </TableCell>
            ))}
          </TableRow>
          {criteria.map((name) => (
            <TableRow key={name}>
              <TableCell>{name}</TableCell>
              {candidates.map((c) => {
                const score = c.scores[name];
                return (
                  <TableCell
                    key={c.application_id}
                    className={`tabular-nums ${score === best(name) ? "font-semibold" : ""}`}
                  >
                    {score != null ? `${score}/10` : "—"}
                    {c.low_confidence.includes(name) && (
                      <span className="ml-1 text-xs text-muted-foreground" title="Some cited evidence wasn't found in the resume">
                        (low confidence)
                      </span>
                    )}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-xs text-muted-foreground">
        Bold = best score on that criterion. Open a candidate to see the evidence behind each score.
      </p>
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense>
      <Comparison />
    </Suspense>
  );
}
