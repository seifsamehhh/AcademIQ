import { ClipboardList, Clock, FileCheck2, CalendarClock } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CourseStatistics as Stats, TaskBreakdown } from "@/lib/types";

function formatAttempted(breakdown: TaskBreakdown): string {
  if (!breakdown.available) {
    return "Not available";
  }
  if (breakdown.total != null) {
    return `${breakdown.attempted ?? 0} of ${breakdown.total} recorded`;
  }
  return `${breakdown.attempted ?? 0} recorded`;
}

function TaskRow({
  icon: Icon,
  label,
  breakdown,
}: {
  icon: typeof ClipboardList;
  label: string;
  breakdown: TaskBreakdown;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-background p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-4 w-4 text-primary" />
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className="text-xs text-muted-foreground">{formatAttempted(breakdown)}</p>
        </div>
      </div>
      <div className="text-right">
        <p className="text-lg font-semibold text-foreground">
          {breakdown.averageScore !== null && breakdown.averageScore !== undefined
            ? `${breakdown.averageScore}%`
            : "—"}
        </p>
        <p className="text-xs text-muted-foreground">avg score</p>
      </div>
    </div>
  );
}

function TimeRow({
  icon: Icon,
  label,
  value,
  hint,
  available,
}: {
  icon: typeof Clock;
  label: string;
  value: string;
  hint?: string;
  available: boolean;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-4">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <div>
        <p className="text-lg font-semibold text-foreground">
          {available ? value : "Not available"}
        </p>
        <p className="text-xs text-muted-foreground">{label}</p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground/80">{hint}</p> : null}
      </div>
    </div>
  );
}

export function CourseStatistics({ stats }: { stats: Stats }) {
  const weeklyEstimated = stats.weeklyAverageEstimated ?? false;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Course Activity Records</CardTitle>
        <CardDescription>
          Activity records are based on synced Moodle data currently available to
          AcademIQ.
        </CardDescription>
        {stats.hasMissingFields ? (
          <p className="text-xs text-muted-foreground pt-1">
            Some Moodle activity fields are not available yet.
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <TaskRow icon={ClipboardList} label="Quizzes" breakdown={stats.quizzes} />
        <TaskRow icon={FileCheck2} label="Assignments" breakdown={stats.assignments} />
        <TimeRow
          icon={Clock}
          label="Total recorded time on course"
          value={
            stats.totalTimeHours != null ? `${stats.totalTimeHours.toFixed(1)} h` : "—"
          }
          available={stats.totalTimeAvailable}
        />
        <TimeRow
          icon={CalendarClock}
          label={
            weeklyEstimated
              ? "Estimated weekly study time"
              : "Average weekly study time"
          }
          value={
            stats.weeklyAverageHours != null
              ? `${stats.weeklyAverageHours.toFixed(1)} h`
              : "—"
          }
          available={stats.weeklyAverageAvailable}
          hint={
            weeklyEstimated && stats.weeklyAverageAvailable
              ? "Estimated from total course time — not from Moodle weekly logs."
              : undefined
          }
        />
      </CardContent>
    </Card>
  );
}
