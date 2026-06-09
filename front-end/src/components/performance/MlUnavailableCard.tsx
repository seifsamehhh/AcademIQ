import { BrainCircuit } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface MlUnavailableCardProps {
  message: string;
}

export function MlUnavailableCard({ message }: MlUnavailableCardProps) {
  return (
    <Card className="border-dashed md:col-span-2">
      <CardHeader>
        <div className="flex items-center gap-2">
          <BrainCircuit className="h-5 w-5 text-muted-foreground" />
          <CardTitle>ML prediction not available</CardTitle>
        </div>
        <CardDescription>
          Course activity stats below are still shown from your synced or seeded data.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed text-muted-foreground">{message}</p>
      </CardContent>
    </Card>
  );
}
