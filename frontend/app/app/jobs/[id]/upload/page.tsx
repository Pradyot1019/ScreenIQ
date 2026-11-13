"use client";

import { FileUp } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ACCEPTED, MAX_FILES, precheck, useBatch, useUploadResumes } from "@/lib/intake";
import { useJob } from "@/lib/jobs";
import type { ParseStatus } from "@/lib/schemas";

const STATUS_VARIANT: Record<ParseStatus, "outline" | "secondary" | "default" | "destructive"> = {
  queued: "outline",
  parsing: "secondary",
  parsed: "default",
  failed: "destructive",
};

export default function UploadPage() {
  const { id } = useParams<{ id: string }>();
  const job = useJob(id);
  const upload = useUploadResumes(id);
  const [batchId, setBatchId] = useState<string | null>(null);
  const batch = useBatch(batchId);
  const [files, setFiles] = useState<File[]>([]);
  const [rejected, setRejected] = useState<{ name: string; reason: string }[]>([]);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    const ok: File[] = [];
    const bad: { name: string; reason: string }[] = [];
    for (const f of Array.from(list)) {
      const reason = precheck(f);
      if (reason) bad.push({ name: f.name, reason });
      else ok.push(f);
    }
    setFiles((prev) => [...prev, ...ok].slice(0, MAX_FILES));
    setRejected(bad);
  }

  async function onUpload() {
    const result = await upload.mutateAsync(files);
    setBatchId(result.id);
    setFiles([]);
  }

  const b = batch.data;
  const finished = b ? b.processed + b.failed : 0;

  return (
    <div className="grid gap-6">
      <div className="grid gap-1">
        <Link href={`/app/jobs/${id}`} className="text-sm text-muted-foreground hover:underline">
          ← {job.data?.title ?? "Job"}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Upload resumes</h1>
        <p className="text-sm text-muted-foreground">
          Up to {MAX_FILES} PDF or DOCX files, 5 MB each. They are parsed in the background.
        </p>
      </div>

      {process.env.NEXT_PUBLIC_DEMO_MODE === "true" && (
        <Alert>
          <AlertDescription>
            Public demo: please upload only fictional or sample resumes, never real people&apos;s.
            Files are processed with Google Gemini&apos;s free tier, which may use them to improve
            Google&apos;s products.
          </AlertDescription>
        </Alert>
      )}

      {!batchId && (
        <>
          <div
            role="button"
            tabIndex={0}
            onClick={() => input.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              addFiles(e.dataTransfer.files);
            }}
            className={`grid cursor-pointer place-items-center gap-2 rounded-xl border-2 border-dashed p-10 text-center ${
              dragging ? "border-primary bg-muted" : "border-border"
            }`}
          >
            <FileUp className="size-8 text-muted-foreground" />
            <p className="text-sm">
              <span className="font-medium">Drop resumes here</span> or click to choose files
            </p>
            <input
              ref={input}
              type="file"
              multiple
              accept={ACCEPTED.join(",")}
              className="hidden"
              onChange={(e) => {
                addFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </div>

          {rejected.length > 0 && (
            <Alert variant="destructive">
              <AlertDescription>
                Skipped: {rejected.map((r) => `${r.name} (${r.reason})`).join("; ")}
              </AlertDescription>
            </Alert>
          )}
          {upload.error && (
            <Alert variant="destructive">
              <AlertDescription>{upload.error.message}</AlertDescription>
            </Alert>
          )}

          {files.length > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm text-muted-foreground">
                {files.length} file{files.length === 1 ? "" : "s"} ready
              </span>
              <Button variant="ghost" onClick={() => setFiles([])}>
                Clear
              </Button>
              <Button className="ml-auto" onClick={onUpload} disabled={upload.isPending}>
                {upload.isPending ? "Uploading…" : `Upload ${files.length}`}
              </Button>
            </div>
          )}
        </>
      )}

      {b && (
        <div className="grid gap-4">
          <div className="grid gap-2">
            <div className="flex justify-between text-sm" aria-live="polite">
              <span>
                {b.status === "done" ? "Done" : "Parsing…"} {finished} / {b.total}
                {b.failed > 0 && ` (${b.failed} failed)`}
              </span>
              {b.status === "done" && (
                <Button variant="link" className="h-auto p-0" onClick={() => setBatchId(null)}>
                  Upload more
                </Button>
              )}
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${b.total ? (finished / b.total) * 100 : 0}%` }}
              />
            </div>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Candidate / reason</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {b.files.map((f) => (
                <TableRow key={f.resume_id}>
                  <TableCell className="font-medium">{f.filename}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[f.status]} className="capitalize">
                      {f.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-normal text-muted-foreground">
                    {f.status === "failed" ? f.error : (f.candidate_name ?? "—")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
