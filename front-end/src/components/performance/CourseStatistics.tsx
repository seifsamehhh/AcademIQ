import { ClipboardList, Clock, FileCheck2, CalendarClock } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  ActivityValueSource,
  CourseStatistics as Stats,
  TaskBreakdown,
} from "@/lib/types";

type TaskLabel = "Quizzes" | "Assignments";

const TASK_UNAVAILABLE_HINT: Record<TaskLabel, string> = {
  Quizzes: "No synced quiz activity data is available for this course yet.",
  Assignments: "No synced assignment activity data is available for this course yet.",
};

function activityFeatureHint(source: ActivityValueSource): string | undefined {
  if (source === "feature_vector") {
    return "From synced activity feature";
  }
  if (source === "estimated_from_synced_activity") {
    return "Estimated from synced Moodle activity";
  }
  return undefined;
}

function formatTaskDisplay(
  breakdown: TaskBreakdown,
  label: TaskLabel,
): {
  countPrimary: string;
  countHint?: string;
  avgPrimary: string;
  avgLabel: string;
} {
  if (!breakdown.available) {
    return {
      countPrimary: "Not available",
      countHint: TASK_UNAVAILABLE_HINT[label],
      avgPrimary: "—",
      avgLabel: "avg score",
    };
  }

  const syncedMoodle = breakdown.valueSource === "synced_moodle";
  const hasAvg =
    breakdown.averageScore !== null && breakdown.averageScore !== undefined;
  const attempted = breakdown.attempted;
  const confirmedZero = syncedMoodle && attempted === 0;
  const countUncertain =
    hasAvg &&
    !confirmedZero &&
    (attempted === null || attempted === 0);

  let countPrimary: string;
  if (countUncertain) {
    countPrimary = "Count not available";
  } else if (confirmedZero) {
    countPrimary =
      breakdown.total != null
        ? `0 of ${breakdown.total} recorded`
        : "0 recorded";
  } else if (breakdown.total != null) {
    countPrimary = `${attempted ?? 0} of ${breakdown.total} recorded`;
  } else {
    countPrimary = `${attempted ?? 0} recorded`;
  }

  const featureHint = activityFeatureHint(breakdown.valueSource);

  return {
    countPrimary,
    countHint: featureHint,
    avgPrimary: hasAvg ? `${breakdown.averageScore}%` : "—",
    avgLabel: hasAvg && countUncertain ? "Synced grade data" : "avg score",
  };
}

function TaskRow({
  icon: Icon,
  label,
  breakdown,
}: {
  icon: typeof ClipboardList;
  label: TaskLabel;
  breakdown: TaskBreakdown;
}) {
  const { countPrimary, countHint, avgPrimary, avgLabel } = formatTaskDisplay(
    breakdown,
    label,
  );

  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-background p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-4 w-4 text-primary" />
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className="text-xs text-muted-foreground">{countPrimary}</p>
          {countHint ? (
            <p className="mt-1 text-xs text-muted-foreground/80">{countHint}</p>
          ) : null}
        </div>
      </div>
      <div className="text-right">
        <p className="text-lg font-semibold text-foreground">{avgPrimary}</p>
        <p className="text-xs text-muted-foreground">{avgLabel}</p>
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
  const totalTimeHint = stats.totalTimeAvailable
    ? activityFeatureHint(stats.totalTimeValueSource)
    : undefined;
  const weeklyHint = stats.weeklyAverageAvailable
    ? weeklyEstimated
      ? activityFeatureHint("estimated_from_synced_activity")
      : activityFeatureHint(stats.weeklyAverageValueSource)
    : undefined;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Course Activity Records</CardTitle>
        <CardDescription>
          Synced course activity signals — not grades.
        </CardDescription>
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
          hint={totalTimeHint}
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
          hint={weeklyHint}
        />
      </CardContent>
    </Card>
  );
}
