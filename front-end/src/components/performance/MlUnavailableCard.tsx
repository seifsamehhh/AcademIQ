import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function MlUnavailableCard({ message }: { message: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Prediction not available yet</CardTitle>
        <CardDescription>
          More course-specific Moodle activity is needed before a reliable prediction
          can be generated.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
      </CardContent>
    </Card>
  );
}
