import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const DEFAULT_MESSAGE =
  "Not enough synced activity data for a reliable prediction yet.";

export function MlUnavailableCard({ message }: { message: string }) {
  const text = message?.trim() || DEFAULT_MESSAGE;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Prediction not available yet</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground leading-relaxed">{text}</p>
      </CardContent>
    </Card>
  );
}
