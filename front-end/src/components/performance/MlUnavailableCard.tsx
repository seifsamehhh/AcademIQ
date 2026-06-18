import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function MlUnavailableCard({ message }: { message: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>ML prediction not available yet</CardTitle>
        <CardDescription>
          Predictions appear only when synced Moodle activity supports a reliable model run.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
      </CardContent>
    </Card>
  );
}
