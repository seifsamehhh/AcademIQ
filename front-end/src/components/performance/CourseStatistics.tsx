import { ClipboardList, Clock, FileCheck2, CalendarClock } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CourseStatistics as Stats, TaskBreakdown } from "@/lib/types";

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
          <p className="text-xs text-muted-foreground">
            {breakdown.attempted} of {breakdown.total} recorded
          </p>
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
}: {
  icon: typeof Clock;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-4">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <div>
        <p className="text-lg font-semibold text-foreground">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground/80">{hint}</p> : null}
      </div>
    </div>
  );
}

export function CourseStatistics({ stats }: { stats: Stats }) {
  const showWeekly =
    stats.weeklyAverageHours !== null && stats.weeklyAverageHours !== undefined;
  const weeklyEstimated = stats.weeklyAverageEstimated ?? false;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Course Activity Records</CardTitle>
        <CardDescription>
          Counts and time from stored activity snapshots — not live Moodle
          dashboards or AI analytics.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <TaskRow icon={ClipboardList} label="Quizzes" breakdown={stats.quizzes} />
        <TaskRow icon={FileCheck2} label="Assignments" breakdown={stats.assignments} />
        <TimeRow
          icon={Clock}
          label="Total recorded time on course"
          value={`${stats.totalTimeHours.toFixed(1)} h`}
        />
        {showWeekly ? (
          <TimeRow
            icon={CalendarClock}
            label={
              weeklyEstimated
                ? "Estimated weekly study time"
                : "Average weekly study time (synced weeks)"
            }
            value={`${stats.weeklyAverageHours!.toFixed(1)} h`}
            hint={
              weeklyEstimated
                ? "Approximation from total course time — not from Moodle weekly logs."
                : undefined
            }
          />
        ) : null}
      </CardContent>
    </Card>
  );
}
