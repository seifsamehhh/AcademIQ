import { TrendingUp, TrendingDown, Minus, Sparkles } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { getPredictedStatus, type PredictedStatus, type Trend } from "@/data/mockData";
import type { CoursePredictionAPI } from "@/types/api";

// ── Styles ──────────────────────────────────────────────────────────────────────

const statusStyles: Record<PredictedStatus, { text: string; dot: string; bar: string }> = {
  Excellent: { text: "text-emerald-600", dot: "bg-emerald-500", bar: "[&>div]:bg-emerald-500" },
  Good:      { text: "text-sky-600",     dot: "bg-sky-500",     bar: "[&>div]:bg-sky-500"     },
  Average:   { text: "text-amber-600",   dot: "bg-amber-500",   bar: "[&>div]:bg-amber-500"   },
  "At Risk": { text: "text-destructive", dot: "bg-destructive", bar: "[&>div]:bg-destructive" },
};

const TrendIconFor = ({ trend }: { trend: Trend }) => {
  if (trend === "up")   return <TrendingUp   className="h-4 w-4 text-emerald-600"     />;
  if (trend === "down") return <TrendingDown  className="h-4 w-4 text-destructive"     />;
  return                       <Minus         className="h-4 w-4 text-muted-foreground" />;
};

// ── Props ───────────────────────────────────────────────────────────────────────

interface CoursePredictedGradesProps {
  /** Predictions from the API (or the fallback mock). */
  predictions: CoursePredictionAPI[];
}

// ── Component ───────────────────────────────────────────────────────────────────

const CoursePredictedGrades = ({ predictions }: CoursePredictedGradesProps) => {
  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Sparkles className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-card-foreground">Predicted Grade per Course</h3>
          <p className="text-xs text-muted-foreground">AI-projected end-of-term scores out of 100.</p>
        </div>
      </div>

      <ul className="divide-y divide-border">
        {predictions.map((c) => {
          const status = getPredictedStatus(c.score);
          const s = statusStyles[status];
          return (
            <li
              key={c.courseId}
              className="grid grid-cols-12 items-center gap-3 py-3 px-2 -mx-2 rounded-lg transition-colors hover:bg-secondary/60"
            >
              <div className="col-span-12 sm:col-span-4 min-w-0">
                <p className="font-medium text-card-foreground truncate">{c.courseName}</p>
                <div className="mt-1 flex items-center gap-2 text-xs">
                  <span className={cn("inline-block h-2 w-2 rounded-full", s.dot)} />
                  <span className={cn("font-medium", s.text)}>{status}</span>
                </div>
              </div>

              <div className="col-span-9 sm:col-span-6">
                <Progress value={c.score} className={cn("h-2 transition-all", s.bar)} />
              </div>

              <div className="col-span-3 sm:col-span-2 flex items-center justify-end gap-2">
                <span className="font-semibold tabular-nums text-card-foreground">
                  {c.score}
                  <span className="text-xs font-normal text-muted-foreground">/100</span>
                </span>
                <TrendIconFor trend={c.trend as Trend} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default CoursePredictedGrades;
