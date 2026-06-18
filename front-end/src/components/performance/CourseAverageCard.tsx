import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

import type { PredictionConfidence } from "@/lib/types";

interface CourseAverageCardProps {
  /** Actual resolved course grade (0-100); null when unavailable. */
  courseAverage: number | null;
  hasGradeData?: boolean;
  /** Predicted grade from ML; null when ML is unavailable. */
  predictedGrade: number | null;
  gradeLabel?: string | null;
  predictionConfidence?: PredictionConfidence | null;
}

export function CourseAverageCard({
  courseAverage,
  hasGradeData = courseAverage !== null,
  predictedGrade,
  gradeLabel,
  predictionConfidence,
}: CourseAverageCardProps) {
  const showComparison =
    hasGradeData && courseAverage !== null && predictedGrade !== null;
  const delta = showComparison ? predictedGrade - courseAverage : 0;
  const limited = predictionConfidence === "limited";

  const deltaLabel = showComparison
    ? limited
      ? delta === 0
        ? "Based on limited synced activity, expected performance matches your current midterm score."
        : delta > 0
          ? `Limited prediction is ${delta.toFixed(1)} pts above your current average.`
          : `Limited prediction is ${Math.abs(delta).toFixed(1)} pts below your current average.`
      : delta === 0
        ? "Prediction matches your current average."
        : delta > 0
          ? `Predicted to rise ${delta.toFixed(1)} pts above your current average.`
          : `Predicted to fall ${Math.abs(delta).toFixed(1)} pts below your current average.`
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Course Average</CardTitle>
        <CardDescription>
          Your actual average across graded Moodle tasks in this course
        </CardDescription>
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
            {gradeLabel ? (
              <p className="text-xs text-muted-foreground">{gradeLabel}</p>
            ) : null}
            {deltaLabel ? (
              <p className="text-sm text-muted-foreground">{deltaLabel}</p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            No grade data available yet.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
