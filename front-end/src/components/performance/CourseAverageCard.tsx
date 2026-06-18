import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

import type { PredictionConfidence } from "@/lib/types";

const GRADE_SOURCE_LABEL: Record<string, string> = {
  midterm_scoring: "Midterm scoring",
  moodle_course_total: "Moodle course total",
  uploaded_transcript: "Uploaded grade transcript",
  graded_items_average: "Average from synced graded tasks",
};

function courseScoreSourceLabel(
  gradeLabel?: string | null,
  gradeSource?: string | null,
): string {
  if (gradeLabel?.trim()) {
    return gradeLabel.trim();
  }
  if (gradeSource && GRADE_SOURCE_LABEL[gradeSource]) {
    return GRADE_SOURCE_LABEL[gradeSource];
  }
  return "Synced grade records";
}

interface CourseAverageCardProps {
  /** Actual resolved course grade (0-100); null when unavailable. */
  courseAverage: number | null;
  hasGradeData?: boolean;
  /** Predicted grade from ML; null when ML is unavailable. */
  predictedGrade: number | null;
  gradeLabel?: string | null;
  gradeSource?: string | null;
  predictionConfidence?: PredictionConfidence | null;
}

export function CourseAverageCard({
  courseAverage,
  hasGradeData = courseAverage !== null,
  predictedGrade,
  gradeLabel,
  gradeSource,
  predictionConfidence,
}: CourseAverageCardProps) {
  const showComparison =
    hasGradeData && courseAverage !== null && predictedGrade !== null;
  const delta = showComparison ? predictedGrade - courseAverage : 0;
  const limited = predictionConfidence === "limited";
  const sourceLabel = courseScoreSourceLabel(gradeLabel, gradeSource);

  const deltaLabel = showComparison
    ? limited
      ? delta === 0
        ? "Based on limited synced activity, expected performance matches your current midterm score."
        : delta > 0
          ? `Limited prediction is ${delta.toFixed(1)} pts above your current score.`
          : `Limited prediction is ${Math.abs(delta).toFixed(1)} pts below your current score.`
      : delta === 0
        ? "Expected performance estimate matches your current score."
        : delta > 0
          ? `Expected performance estimate is ${delta.toFixed(1)} pts above your current score.`
          : `Expected performance estimate is ${Math.abs(delta).toFixed(1)} pts below your current score.`
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Current course score</CardTitle>
        <CardDescription>From {sourceLabel}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {hasGradeData && courseAverage !== null ? (
          <>
            <div className="flex items-baseline gap-1">
              <span className="text-4xl font-bold text-foreground">
                {courseAverage.toFixed(1)}
              </span>
              <span className="text-lg text-muted-foreground">/ 100</span>
            </div>
            <Progress
              value={courseAverage}
              indicatorClassName="bg-muted-foreground"
            />
            {deltaLabel ? (
              <p className="text-sm text-muted-foreground">{deltaLabel}</p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            No current course score is available yet.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
