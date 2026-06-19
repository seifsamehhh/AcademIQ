import {
  Activity,
  BookOpen,
  ClipboardCheck,
  Clock,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CourseStatistics as Stats } from "@/lib/types";

function MetricCard({
  icon: Icon,
  title,
  value,
  hint,
}: {
  icon: typeof Activity;
  title: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-4 w-4 text-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">{title}</p>
          <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
          {hint ? (
            <p className="mt-1 text-xs text-muted-foreground/80">{hint}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function formatTaskCount(
  attempted: number | null | undefined,
  total: number | null | undefined,
  available: boolean,
): string {
  if (!available) return "Not enough synced data";
  if (attempted === 0 && total === 0) return "0 recorded";
  if (total != null) return `${attempted ?? 0} of ${total} recorded`;
  return `${attempted ?? 0} recorded`;
}

export function CourseStatistics({ stats }: { stats: Stats }) {
  const engagementValue = stats.weeklyAverageAvailable
    ? stats.weeklyAverageHours != null
      ? `${stats.weeklyAverageHours.toFixed(1)} h / week`
      : "Not enough synced data"
    : "Not enough synced data";

  const engagementHint = stats.weeklyAverageEstimated
    ? "Estimated from synced course time"
    : stats.weeklyAverageAvailable
      ? "From synced Moodle activity"
      : undefined;

  const materialValue = formatTaskCount(
    stats.quizzes.attempted,
    stats.quizzes.total,
    stats.quizzes.available,
  );
  const materialHint = stats.quizzes.available
    ? stats.quizzes.averageScore != null
      ? `Avg quiz score ${stats.quizzes.averageScore}%`
      : "Quiz views and attempts"
    : undefined;

  const assessmentValue = formatTaskCount(
    stats.assignments.attempted,
    stats.assignments.total,
    stats.assignments.available,
  );
  const assessmentHint = stats.assignments.available
    ? stats.assignments.averageScore != null
      ? `Avg assignment score ${stats.assignments.averageScore}%`
      : "Assignment submissions"
    : undefined;

  const timingValue = stats.totalTimeAvailable
    ? stats.totalTimeHours != null
      ? `${stats.totalTimeHours.toFixed(1)} h total`
      : "Not enough synced data"
    : "Not enough synced data";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Course Activity Metrics</CardTitle>
        <CardDescription>
          Synced Moodle activity signals used by the performance model
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <MetricCard
          icon={Activity}
          title="Engagement Activity"
          value={engagementValue}
          hint={engagementHint}
        />
        <MetricCard
          icon={BookOpen}
          title="Material Interaction"
          value={materialValue}
          hint={materialHint}
        />
        <MetricCard
          icon={ClipboardCheck}
          title="Assessment Activity"
          value={assessmentValue}
          hint={assessmentHint}
        />
        <MetricCard
          icon={Clock}
          title="Timing Behavior"
          value={timingValue}
          hint={
            stats.totalTimeAvailable ? "Total recorded time on course" : undefined
          }
        />
      </CardContent>
    </Card>
  );
}
