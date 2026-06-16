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

/** Map backend quizStatus → { label, variant } */
function statusBadge(material: LearningMaterial): { label: string; variant: "default" | "muted" | "destructive" | "warning" } {
  switch (material.quizStatus) {
    case "ready":
      return { label: "Ready for quiz", variant: "default" };
    case "not_uploaded":
      return { label: "Not uploaded yet", variant: "muted" };
    case "extraction_failed":
      return { label: "Extraction failed", variant: "destructive" };
    case "too_short":
      return { label: "Too little content", variant: "warning" };
    case "not_quiz_material":
      return { label: "Not quiz material", variant: "muted" };
    default:
      // Fallback for older API responses that don't include quizStatus
      if (material.hasContent) return { label: "Ready for quiz", variant: "default" };
      if (material.contentNote?.startsWith("No readable text")) return { label: "Not uploaded yet", variant: "muted" };
      return { label: "Content unavailable", variant: "muted" };
  }
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
          Materials with extracted text are selectable. Works with lectures, labs,
          revisions, slides, and any uploaded PDF or PPTX. Grades files and Moodle
          activity types are shown but cannot be used for quiz generation.
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
            const { label: statusLabel, variant: statusVariant } = statusBadge(material);

            return (
              <label
                key={material.id}
                className={cn(
                  "flex flex-wrap items-center gap-3 rounded-lg border border-border bg-background p-3 transition-colors",
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

                <Badge variant={statusVariant}>{statusLabel}</Badge>

                {material.source === "moodle_sync" ? (
                  <Badge variant="muted">Moodle</Badge>
                ) : null}
                <Badge variant="muted">{material.kind}</Badge>

                {!selectable && (material.contentNote || material.quizStatusReason) ? (
                  <p className="w-full basis-full pl-9 text-xs text-muted-foreground">
                    {material.quizStatusReason || material.contentNote}
                  </p>
                ) : null}
              </label>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
