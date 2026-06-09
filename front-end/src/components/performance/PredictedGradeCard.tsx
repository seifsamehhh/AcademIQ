import { Target } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

export function PredictedGradeCard({ grade }: { grade: number | null }) {
  if (grade === null) return null;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" />
          <CardTitle>Predicted Grade</CardTitle>
        </div>
        <CardDescription>From the grade-prediction model</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline gap-1">
          <span className="text-4xl font-bold text-foreground">
            {grade.toFixed(0)}
          </span>
          <span className="text-lg text-muted-foreground">/ 100</span>
        </div>
        <Progress value={grade} />
      </CardContent>
    </Card>
  );
}
