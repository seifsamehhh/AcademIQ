import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function LimitedInsightCard({ message }: { message: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Prediction not available yet</CardTitle>
        <CardDescription>
          Not enough synced activity data for this course.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {message?.trim() ||
            "More Moodle activity signals are needed before a model estimate can be shown."}
        </p>
      </CardContent>
    </Card>
  );
}
