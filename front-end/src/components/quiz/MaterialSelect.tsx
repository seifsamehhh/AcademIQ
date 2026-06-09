import { FileText } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { LearningMaterial } from "@/lib/types";

interface MaterialSelectProps {
  materials: LearningMaterial[];
  selectedIds: string[];
  onToggle: (id: string) => void;
}

export function MaterialSelect({
  materials,
  selectedIds,
  onToggle,
}: MaterialSelectProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Select Learning Materials</CardTitle>
        <CardDescription>
          Only materials with available content can be used for quiz generation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {materials.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No learning materials found for this course.
          </p>
        ) : (
          materials.map((material) => {
            const selectable = material.hasContent;
            const checked = selectedIds.includes(material.id);
            return (
              <label
                key={material.id}
                className={cn(
                  "flex items-center gap-3 rounded-lg border border-border bg-background p-3 transition-colors",
                  selectable
                    ? "cursor-pointer hover:bg-accent has-[:checked]:border-primary/50"
                    : "cursor-not-allowed opacity-70",
                )}
              >
                <Checkbox
                  checked={checked}
                  disabled={!selectable}
                  onChange={() => {
                    if (selectable) onToggle(material.id);
                  }}
                />
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="flex-1 text-sm font-medium text-foreground">
                  {material.title}
                </span>
                {selectable ? (
                  <Badge variant="default">Ready for quiz</Badge>
                ) : (
                  <Badge variant="muted">Content not available</Badge>
                )}
                <Badge variant="muted">{material.kind}</Badge>
              </label>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
