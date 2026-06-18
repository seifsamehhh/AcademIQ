import { Lightbulb } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { RiskFactor } from "@/lib/types";

type RiskLevel = "High" | "Medium" | "Low";

/** Map a 0-100 impact score to a human risk level + matching theme colors. */
function riskLevel(impact: number): {
  level: RiskLevel;
  badge: "destructive" | "warning" | "default";
  indicator: string;
} {
  if (impact >= 60) {
    return { level: "High", badge: "destructive", indicator: "bg-destructive" };
  }
  if (impact >= 35) {
    return { level: "Medium", badge: "warning", indicator: "bg-warning" };
  }
  return { level: "Low", badge: "default", indicator: "bg-primary" };
}

interface Props {
  /** 1-based rank shown in the leading badge. */
  rank: number;
  factor: RiskFactor;
}

/**
 * A single insight card: title, reason, impact/severity, and recommendation.
 */
export function RiskFactorCard({ rank, factor }: Props) {
  const { level, badge, indicator } = riskLevel(factor.impact);

  return (
    <div className="rounded-lg border border-border bg-background p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground">
            {rank}
          </span>
          <p className="font-medium text-foreground">{factor.title}</p>
        </div>
        <Badge variant={badge} className="shrink-0">
          {level} · {factor.impact}
        </Badge>
      </div>

      <div className="mt-2 space-y-1 sm:ml-9">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Reason
        </p>
        <p className="text-sm text-muted-foreground">{factor.description}</p>
      </div>

      <Progress
        value={factor.impact}
        indicatorClassName={cn(indicator)}
        className="mt-3 sm:ml-9"
      />

      <div className="mt-4 flex items-start gap-3 rounded-lg border border-primary/20 bg-primary/5 p-3 sm:ml-9">
        <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <div className="space-y-0.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">
            Recommendation
          </p>
          <p className="text-sm text-foreground">{factor.recommendation}</p>
        </div>
      </div>
    </div>
  );
}
