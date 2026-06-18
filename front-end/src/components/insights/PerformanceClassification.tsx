import { CheckCircle2, AlertCircle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PerformanceStatus } from "@/lib/types";

interface Props {
  isHighPerformer: boolean;
  summary: string;
  ruleBased?: boolean;
  performanceStatus?: PerformanceStatus | null;
  classificationSource?: string | null;
}

const STATUS_LABEL: Record<PerformanceStatus, string> = {
  Good: "Strong engagement signals",
  Average: "Room to improve",
  "At Risk": "At Risk",
};

export function PerformanceClassification({
  isHighPerformer,
  summary,
  ruleBased = true,
  performanceStatus,
  classificationSource,
}: Props) {
  const Icon = isHighPerformer ? CheckCircle2 : AlertCircle;
  const badgeLabel = performanceStatus
    ? STATUS_LABEL[performanceStatus]
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
          <CardTitle>
            {ruleBased ? "Performance guidance" : "Performance classification"}
          </CardTitle>
        </div>
        <CardDescription>
          {classificationSource ??
            (ruleBased
              ? "Rule-based analysis from synced Moodle activity records"
              : "How the performance model classifies you in this course")}
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
