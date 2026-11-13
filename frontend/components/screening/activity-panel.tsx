"use client";

import { useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useAddNote, useNotes } from "@/lib/applications";
import { STAGE_LABELS, type ApplicationDetail } from "@/lib/schemas";

const when = (iso: string) => new Date(iso).toLocaleString();

/** Notes (any member, including viewers) and the stage history. */
export function ActivityPanel({
  applicationId,
  history,
}: {
  applicationId: string;
  history: ApplicationDetail["history"];
}) {
  const notes = useNotes(applicationId);
  const add = useAddNote(applicationId);
  const [draft, setDraft] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    await add.mutateAsync(draft);
    setDraft("");
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Notes</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          {notes.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">No notes yet.</p>
          )}
          {notes.data?.map((n) => (
            <div key={n.id} className="grid gap-0.5 text-sm">
              <p className="whitespace-pre-wrap">{n.body}</p>
              <p className="text-xs text-muted-foreground">
                {n.author_name ?? "Former member"} · {when(n.created_at)}
              </p>
            </div>
          ))}
          <form onSubmit={onSubmit} className="grid gap-2">
            <label htmlFor="note" className="sr-only">
              Add a note
            </label>
            <Textarea
              id="note"
              rows={3}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Add a note for your team…"
            />
            {add.error && (
              <Alert variant="destructive">
                <AlertDescription>{add.error.message}</AlertDescription>
              </Alert>
            )}
            <Button type="submit" className="justify-self-end" disabled={add.isPending || !draft.trim()}>
              {add.isPending ? "Saving…" : "Add note"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Stage history</CardTitle>
        </CardHeader>
        <CardContent>
          {history.length === 0 ? (
            <p className="text-sm text-muted-foreground">No stage changes yet.</p>
          ) : (
            <ol className="grid gap-2 text-sm">
              {history.map((h, i) => (
                <li key={i}>
                  {STAGE_LABELS[h.from_stage]} → <strong>{STAGE_LABELS[h.to_stage]}</strong>
                  <span className="block text-xs text-muted-foreground">
                    {h.actor_name ?? "AI screening"} · {when(h.created_at)}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
