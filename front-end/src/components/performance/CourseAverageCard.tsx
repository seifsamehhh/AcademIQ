import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface CourseAverageCardProps {
  /** Actual current average (0-100); null when no Moodle grades exist. */
  courseAverage: number | null;
  hasGradeData?: boolean;
  /** Predicted grade from ML; null when ML is unavailable. */
  predictedGrade: number | null;
}

export function CourseAverageCard({
  courseAverage,
  hasGradeData = courseAverage !== null,
  predictedGrade,
}: CourseAverageCardProps) {
  const showComparison =
    hasGradeData && courseAverage !== null && predictedGrade !== null;
  const delta = showComparison ? predictedGrade - courseAverage : 0;
  const deltaLabel = showComparison
    ? delta === 0
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
            {deltaLabel ? (
              <p className="text-sm text-muted-foreground">{deltaLabel}</p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            No grade data available yet. Sync Moodle grades with the Chrome
            extension to see your course average here.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
