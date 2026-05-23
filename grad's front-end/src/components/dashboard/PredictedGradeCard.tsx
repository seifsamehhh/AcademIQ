import { TrendingUp, TrendingDown, Minus, Sparkles } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface PredictedGradeCardProps {
  score: number; // 0-100
  trend?: "up" | "down" | "flat";
}

const getLabel = (s: number) => {
  if (s >= 85) return { label: "Excellent", color: "text-emerald-600", bar: "bg-emerald-500" };
  if (s >= 75) return { label: "Good", color: "text-sky-600", bar: "bg-sky-500" };
  if (s >= 65) return { label: "Average", color: "text-amber-600", bar: "bg-amber-500" };
  return { label: "At Risk", color: "text-destructive", bar: "bg-destructive" };
};

const PredictedGradeCard = ({ score, trend = "up" }: PredictedGradeCardProps) => {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const meta = getLabel(clamped);
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor =
    trend === "up" ? "text-emerald-600" : trend === "down" ? "text-destructive" : "text-muted-foreground";

  return (
    <div className="group rounded-xl border border-border bg-card p-6 transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <Sparkles className="h-6 w-6 text-primary" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">Predicted Grade</p>
          <p className={cn("text-xl font-bold", meta.color)}>{meta.label}</p>
        </div>
        <TrendIcon className={cn("h-5 w-5", trendColor)} />
      </div>

      <div className="mb-3 flex items-baseline justify-between">
        <span className="text-4xl font-bold text-card-foreground tabular-nums">
          {clamped}
          <span className="text-lg font-medium text-muted-foreground">/100</span>
        </span>
        <span className={cn("text-sm font-medium", trendColor)}>
          {trend === "up" ? "+" : trend === "down" ? "-" : ""}
          {trend !== "flat" ? "2.4%" : "0%"} vs last
        </span>
      </div>

      <Progress value={clamped} className="h-2" />
      <p className="mt-3 text-xs text-muted-foreground">
        AI-projected end-of-term score based on recent performance.
      </p>
    </div>
  );
};

export default PredictedGradeCard;