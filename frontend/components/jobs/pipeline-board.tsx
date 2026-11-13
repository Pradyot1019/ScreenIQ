"use client";

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import Link from "next/link";
import { KnockoutBadge, RecommendationBadge } from "@/components/screening/badges";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useApplications, useMoveStage } from "@/lib/applications";
import { STAGES, STAGE_LABELS, StageSchema, type ApplicationRow, type Stage } from "@/lib/schemas";

function Card({ app, draggable }: { app: ApplicationRow; draggable: boolean }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: app.id,
    disabled: !draggable,
  });
  const s = app.screening;
  return (
    <div
      ref={setNodeRef}
      style={transform ? { transform: `translate(${transform.x}px, ${transform.y}px)` } : undefined}
      className={`grid gap-1 rounded-lg border bg-card p-2 text-sm shadow-xs ${
        draggable ? "cursor-grab" : ""
      } ${isDragging ? "z-10 opacity-80 shadow-md" : ""}`}
      {...attributes}
      {...listeners}
    >
      <Link
        href={`/app/applications/${app.id}`}
        className="font-medium hover:underline"
        onPointerDown={(e) => e.stopPropagation()} // let the link click, not start a drag
      >
        {app.candidate.full_name ?? "Unnamed"}
      </Link>
      <div className="flex flex-wrap items-center gap-1">
        {s?.status === "done" && s.overall_score != null && (
          <span className="tabular-nums text-muted-foreground">{Math.round(s.overall_score)}</span>
        )}
        {s?.recommendation && <RecommendationBadge value={s.recommendation} />}
        {s?.knockout_failed && <KnockoutBadge />}
      </div>
    </div>
  );
}

function Column({
  stage,
  apps,
  canWrite,
}: {
  stage: Stage;
  apps: ApplicationRow[];
  canWrite: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  return (
    <section
      ref={setNodeRef}
      aria-label={`${STAGE_LABELS[stage]} (${apps.length})`}
      className={`grid min-h-40 w-56 shrink-0 content-start gap-2 rounded-xl border p-2 ${
        isOver ? "border-primary bg-muted" : "bg-muted/40"
      }`}
    >
      <h3 className="flex justify-between px-1 text-sm font-medium">
        {STAGE_LABELS[stage]}
        <span className="text-muted-foreground">{apps.length}</span>
      </h3>
      {apps.map((a) => (
        <Card key={a.id} app={a} draggable={canWrite} />
      ))}
    </section>
  );
}

export function PipelineBoard({ jobId, canWrite }: { jobId: string; canWrite: boolean }) {
  const apps = useApplications(jobId);
  const move = useMoveStage(jobId);
  // A 5px threshold so a plain click on a card isn't treated as a drag; keyboard users
  // can pick a card up with Space and move it with the arrow keys.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  );

  function onDragEnd({ active, over }: DragEndEvent) {
    const target = StageSchema.safeParse(over?.id);
    const app = apps.data?.find((a) => a.id === active.id);
    if (!target.success || !app || app.stage === target.data) return;
    move.mutate({ id: app.id, stage: target.data });
  }

  if (apps.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <div className="grid gap-3">
      {move.error && (
        <Alert variant="destructive">
          <AlertDescription>Couldn&apos;t move the candidate: {move.error.message}</AlertDescription>
        </Alert>
      )}
      <p className="text-xs text-muted-foreground">
        {canWrite
          ? "Drag candidates between stages. Only people move candidates; the AI never rejects anyone."
          : "Read-only: only owners and recruiters can move candidates."}
      </p>
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="flex gap-3 overflow-x-auto pb-2">
          {STAGES.map((stage) => (
            <Column
              key={stage}
              stage={stage}
              apps={(apps.data ?? []).filter((a) => a.stage === stage)}
              canWrite={canWrite}
            />
          ))}
        </div>
      </DndContext>
    </div>
  );
}
