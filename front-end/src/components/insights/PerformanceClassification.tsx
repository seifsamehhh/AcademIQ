import { CheckCircle2, AlertCircle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PerformanceStatus } from "@/lib/types";

interface Props {
  isHighPerformer: boolean;
  summary: string;
  ruleBased?: boolean;
  performanceStatus?: PerformanceStatus | null;
}

const STATUS_LABEL: Partial<Record<string, string>> = {
  Good: "Strong engagement signals",
  "On Track": "On Track",
  Average: "Room to improve",
  "Room to improve": "Room to improve",
  "At Risk": "At Risk",
};

export function PerformanceClassification({
  isHighPerformer,
  summary,
  ruleBased = true,
  performanceStatus,
}: Props) {
  const Icon = isHighPerformer ? CheckCircle2 : AlertCircle;
  const badgeLabel = performanceStatus
    ? STATUS_LABEL[performanceStatus] ?? performanceStatus
    : isHighPerformer
      ? "Strong engagement signals"
      : "Room to improve";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Icon
            className={isHighPerformer ? "h-5 w-5 text-success" : "h-5 w-5 text-warning"}
          />
          <CardTitle>Performance guidance</CardTitle>
        </div>
        <CardDescription>
          Insights source: available course signals
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Badge variant={isHighPerformer ? "success" : "warning"} className="text-sm">
          {badgeLabel}
        </Badge>
        <p className="text-sm text-muted-foreground">{summary}</p>
      </CardContent>
    </Card>
  );
}
