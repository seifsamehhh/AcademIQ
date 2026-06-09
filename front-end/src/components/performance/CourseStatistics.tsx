import { ClipboardList, Clock, FileCheck2, CalendarClock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
            {breakdown.attempted} of {breakdown.total} attempted
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
}: {
  icon: typeof Clock;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-4">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <div>
        <p className="text-lg font-semibold text-foreground">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

export function CourseStatistics({ stats }: { stats: Stats }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Course Statistics</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <TaskRow icon={ClipboardList} label="Quizzes" breakdown={stats.quizzes} />
        <TaskRow icon={FileCheck2} label="Assignments" breakdown={stats.assignments} />
        <TimeRow
          icon={Clock}
          label="Total time on course"
          value={`${stats.totalTimeHours.toFixed(1)} h`}
        />
        <TimeRow
          icon={CalendarClock}
          label="Weekly-average study time"
          value={`${stats.weeklyAverageHours.toFixed(1)} h`}
        />
      </CardContent>
    </Card>
  );
}
