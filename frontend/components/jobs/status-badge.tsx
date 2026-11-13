import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/schemas";

const VARIANT = { draft: "outline", open: "default", closed: "secondary" } as const;

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <Badge variant={VARIANT[status]} className="capitalize">
      {status}
    </Badge>
  );
}
