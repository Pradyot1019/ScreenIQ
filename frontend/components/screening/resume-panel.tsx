"use client";

import { ExternalLink } from "lucide-react";
import { Fragment } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useResume } from "@/lib/applications";
import type { ResumeView } from "@/lib/schemas";

/** Split the text into plain and highlighted pieces. Overlapping spans are skipped. */
function segments(view: ResumeView) {
  const parts: { text: string; criterion?: string }[] = [];
  let cursor = 0;
  for (const h of view.highlights) {
    if (h.start < cursor) continue; // overlaps the previous highlight
    if (h.start > cursor) parts.push({ text: view.text.slice(cursor, h.start) });
    parts.push({ text: view.text.slice(h.start, h.end), criterion: h.criterion });
    cursor = h.end;
  }
  parts.push({ text: view.text.slice(cursor) });
  return parts;
}

export function ResumePanel({
  applicationId,
  screeningId,
}: {
  applicationId: string;
  screeningId: string | undefined;
}) {
  const resume = useResume(applicationId, screeningId);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="text-base">Resume</CardTitle>
        {resume.data?.url && (
          <Button asChild variant="outline" size="sm">
            {/* Signed URL: valid for 5 minutes, for this one file only. */}
            <a href={resume.data.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink /> Open original ({resume.data.filename})
            </a>
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {resume.isPending ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : resume.isError ? (
          <p className="text-sm text-destructive">{resume.error.message}</p>
        ) : (
          <>
            {resume.data.highlights.length > 0 && (
              <p className="mb-3 text-xs text-muted-foreground">
                Highlighted: the exact passages the AI cited as evidence (hover for the criterion).
              </p>
            )}
            <pre className="max-h-[32rem] overflow-y-auto font-sans text-sm leading-relaxed whitespace-pre-wrap">
              {segments(resume.data).map((part, i) =>
                part.criterion ? (
                  <mark
                    key={i}
                    title={`Evidence for: ${part.criterion}`}
                    className="rounded-sm bg-yellow-200/70 px-0.5 text-foreground dark:bg-yellow-500/30"
                  >
                    {part.text}
                  </mark>
                ) : (
                  <Fragment key={i}>{part.text}</Fragment>
                ),
              )}
            </pre>
          </>
        )}
      </CardContent>
    </Card>
  );
}
