import { Badge } from "@/components/ui/badge";
import type { Recommendation } from "@/lib/schemas";

const REC = {
  strong: { label: "Strong fit", variant: "default" },
  possible: { label: "Possible fit", variant: "secondary" },
  weak: { label: "Weak fit", variant: "outline" },
} as const;

export function RecommendationBadge({ value }: { value: Recommendation }) {
  return <Badge variant={REC[value].variant}>{REC[value].label}</Badge>;
}

export function KnockoutBadge() {
  return (
    <Badge variant="destructive" title="A must-have criterion wasn't met. Review before deciding.">
      Must-have missing
    </Badge>
  );
}

/** Score out of 100 with a small bar, so a column of them can be compared at a glance. */
export function ScoreBar({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-10 text-right font-medium tabular-nums">{Math.round(score)}</span>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div className="h-full bg-primary" style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}
