import { Target } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { PredictionConfidence } from "@/lib/types";

function confidenceNote(confidence?: PredictionConfidence | null): string {
  if (confidence === "limited") {
    return "Limited confidence because some Moodle activity signals are missing.";
  }
  return "Model estimate based on available activity features.";
}

export function PredictedGradeCard({
  grade,
  confidence,
}: {
  grade: number | null;
  predictionSource?: string | null;
  confidence?: PredictionConfidence | null;
}) {
  if (grade === null) return null;
  const confidenceLabel =
    confidence === "high" ? "High" : confidence === "limited" ? "Limited" : null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" />
          <CardTitle>Predicted Grade</CardTitle>
        </div>
        <CardDescription>
          Predicted from synced engagement, assessment activity, timing behavior, and
          learning activity signals.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline gap-1">
          <span className="text-4xl font-bold text-foreground">
            {grade.toFixed(0)}
          </span>
          <span className="text-lg text-muted-foreground">/ 100</span>
        </div>
        <Progress value={grade} />
        {confidenceLabel ? (
          <Badge variant={confidence === "high" ? "default" : "muted"}>
            Confidence: {confidenceLabel}
          </Badge>
        ) : null}
        <p className="text-xs text-muted-foreground leading-relaxed">
          {confidenceNote(confidence)}
        </p>
      </CardContent>
    </Card>
  );
}
