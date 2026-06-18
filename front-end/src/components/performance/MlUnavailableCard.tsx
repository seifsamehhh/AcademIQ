import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function MlUnavailableCard({ message }: { message: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Prediction not available yet</CardTitle>
        <CardDescription>
          Not enough synced Moodle activity data for a reliable prediction.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {message ? (
          <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
