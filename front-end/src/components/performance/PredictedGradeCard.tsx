import { Target } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { PredictionConfidence } from "@/lib/types";

const LIMITED_SOURCE_NOTE =
  "Prediction based on current grade records and limited synced activity features.";

function predictionSourceLabel(
  predictionSource?: string | null,
  confidence?: PredictionConfidence | null,
): string | null {
  if (confidence === "limited") {
    return LIMITED_SOURCE_NOTE;
  }
  if (predictionSource === "rule_adjusted_prediction") {
    return "Limited activity estimate";
  }
  if (predictionSource === "ml_service" || predictionSource === "local_ml") {
    return "ML prediction";
  }
  return null;
}

export function PredictedGradeCard({
  grade,
  predictionSource,
  confidence,
}: {
  grade: number | null;
  predictionSource?: string | null;
  confidence?: PredictionConfidence | null;
}) {
  if (grade === null) return null;
  const confidenceLabel =
    confidence === "high" ? "High" : confidence === "limited" ? "Limited" : null;
  const sourceLabel = predictionSourceLabel(predictionSource, confidence);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" />
          <CardTitle>Predicted Grade</CardTitle>
        </div>
        <CardDescription>
          Expected performance estimate — not your official Moodle grade or midterm score.
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
        {sourceLabel ? (
          <p className="text-xs text-muted-foreground">{sourceLabel}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
