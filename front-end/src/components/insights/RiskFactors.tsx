import { TrendingDown } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RiskFactorCard } from "./RiskFactorCard";
import type { RiskFactor } from "@/lib/types";

export function RiskFactors({
  factors,
  ruleBased = true,
}: {
  factors: RiskFactor[];
  ruleBased?: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <TrendingDown className="h-5 w-5 text-destructive" />
          <CardTitle>{ruleBased ? "Guidance Factors" : "Risk Factors"}</CardTitle>
        </div>
        <CardDescription>
          Insights source: available course signals. Ranked by estimated impact on
          performance — each with a suggested next step.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {factors.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No significant risk factors detected for this course.
          </p>
        ) : (
          factors.map((factor, i) => (
            <RiskFactorCard key={factor.title} rank={i + 1} factor={factor} />
          ))
        )}
      </CardContent>
    </Card>
  );
}
