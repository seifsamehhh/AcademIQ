import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function LimitedInsightCard({ message }: { message: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Rule-based performance insight</CardTitle>
        <CardDescription>
          Guidance from synced activity — no numeric ML prediction is shown.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
      </CardContent>
    </Card>
  );
}
