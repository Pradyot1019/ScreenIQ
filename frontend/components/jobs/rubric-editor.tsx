"use client";

import { Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useGenerateRubric, useSaveRubric } from "@/lib/jobs";
import { CriterionTypeSchema, type Criterion, type Job } from "@/lib/schemas";

const toRows = (job: Job): Criterion[] =>
  job.criteria.map(({ name, description, type, weight, is_knockout }) => ({
    name,
    description,
    type,
    weight,
    is_knockout,
  }));

const EMPTY_ROW: Criterion = {
  name: "",
  description: "",
  type: "skill",
  weight: 0,
  is_knockout: false,
};

export function RubricEditor({ job, editable }: { job: Job; editable: boolean }) {
  const [rows, setRows] = useState<Criterion[]>(() => toRows(job));
  const [fromAi, setFromAi] = useState(false);
  const generate = useGenerateRubric(job.id);
  const save = useSaveRubric(job.id);

  const total = rows.reduce((sum, r) => sum + (Number.isFinite(r.weight) ? r.weight : 0), 0);
  const dirty = JSON.stringify(rows) !== JSON.stringify(toRows(job));
  const canSave = editable && dirty && total === 100 && rows.every((r) => r.name.trim());

  const update = (i: number, patch: Partial<Criterion>) =>
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  async function onGenerate() {
    if (dirty && rows.length && !confirm("Replace the current rubric with an AI draft?")) return;
    const draft = await generate.mutateAsync();
    setRows(draft.criteria);
    setFromAi(true);
  }

  async function onSave() {
    await save.mutateAsync(rows);
    setFromAi(false);
  }

  const error = generate.error ?? save.error;

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Scoring rubric</h2>
          <p className="text-sm text-muted-foreground">
            Weights must add up to 100. Knockouts are must-haves: missing one flags the candidate
            (it never rejects them automatically).
          </p>
        </div>
        {editable && (
          <Button variant="outline" onClick={onGenerate} disabled={generate.isPending}>
            <Sparkles />
            {generate.isPending ? "Drafting…" : "Draft with AI"}
          </Button>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}
      {fromAi && dirty && (
        <Alert>
          <AlertDescription>
            AI draft. Review the criteria and weights, then save. Nothing is saved until you do.
          </AlertDescription>
        </Alert>
      )}

      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No rubric yet.{editable && " Draft one with AI from the job description, or add criteria."}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40%]">Criterion</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="w-24">Weight</TableHead>
              <TableHead>Knockout</TableHead>
              {editable && <TableHead className="sr-only">Remove</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow key={i}>
                <TableCell className="align-top">
                  <Input
                    aria-label={`Criterion ${i + 1} name`}
                    value={row.name}
                    disabled={!editable}
                    onChange={(e) => update(i, { name: e.target.value })}
                  />
                  {row.description && (
                    <p className="mt-1 text-xs whitespace-normal text-muted-foreground">
                      {row.description}
                    </p>
                  )}
                </TableCell>
                <TableCell className="align-top">
                  <select
                    aria-label={`Criterion ${i + 1} type`}
                    value={row.type}
                    disabled={!editable}
                    onChange={(e) =>
                      update(i, { type: CriterionTypeSchema.parse(e.target.value) })
                    }
                    className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm capitalize"
                  >
                    {CriterionTypeSchema.options.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </TableCell>
                <TableCell className="align-top">
                  <Input
                    aria-label={`Criterion ${i + 1} weight`}
                    type="number"
                    min={0}
                    max={100}
                    value={Number.isFinite(row.weight) ? row.weight : ""}
                    disabled={!editable}
                    onChange={(e) => update(i, { weight: e.target.valueAsNumber })}
                  />
                </TableCell>
                <TableCell className="align-top">
                  <Checkbox
                    aria-label={`Criterion ${i + 1} is a knockout`}
                    checked={row.is_knockout}
                    disabled={!editable}
                    onCheckedChange={(v) => update(i, { is_knockout: v === true })}
                    className="mt-2"
                  />
                </TableCell>
                {editable && (
                  <TableCell className="align-top">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove criterion ${i + 1}`}
                      onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
                    >
                      <Trash2 />
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {editable && (
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" onClick={() => setRows((prev) => [...prev, { ...EMPTY_ROW }])}>
            Add criterion
          </Button>
          <span
            className={`text-sm ${total === 100 ? "text-muted-foreground" : "text-destructive"}`}
            aria-live="polite"
          >
            Total weight: {total} / 100
          </span>
          <Button className="ml-auto" onClick={onSave} disabled={!canSave || save.isPending}>
            {save.isPending ? "Saving…" : "Save rubric"}
          </Button>
        </div>
      )}
    </div>
  );
}
