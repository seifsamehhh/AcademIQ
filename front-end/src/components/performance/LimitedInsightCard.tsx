import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function LimitedInsightCard({ message }: { message: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance insight</CardTitle>
        <CardDescription>
          Based on current grade records and available activity signals.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
      </CardContent>
    </Card>
  );
}
