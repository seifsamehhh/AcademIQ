import { Award } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { performanceStyle } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { PerformanceStatus } from "@/lib/types";

const COPY: Record<PerformanceStatus, string> = {
  Good: "You're tracking well in this course. Keep your current pace.",
  Average: "Solid footing with room to push into the high-performer band.",
  "At Risk": "This course needs attention. Review the insights for what to fix first.",
};

export function PerformanceStatusCard({
  status,
}: {
  status: PerformanceStatus | null;
}) {
  if (!status) return null;
  const style = performanceStyle(status);
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Award className={cn("h-5 w-5", style.text)} />
          <CardTitle>Performance Status</CardTitle>
        </div>
        <CardDescription>From the student-clustering model</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Badge variant={style.variant} className="text-sm">
          {status}
        </Badge>
        <p className="text-sm text-muted-foreground">{COPY[status]}</p>
      </CardContent>
    </Card>
  );
}
