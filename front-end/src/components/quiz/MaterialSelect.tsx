import { useState } from "react";
import { ChevronDown, ChevronRight, FileText } from "lucide-react";
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

/**
 * A material is selectable when it either has enough content on its own
 * ("ready") OR is educational with limited text that can use course-context
 * fallback ("extraction_too_short").
 */
function isSelectable(m: LearningMaterial): boolean {
  if (m.quizStatus === "ready") return true;
  if (m.quizStatus === "extraction_too_short") return true;
  // Older API responses that don't include quizStatus
  if (!m.quizStatus && m.hasContent) return true;
  return false;
}

/** Badge label + color variant for each quiz status */
function statusBadge(m: LearningMaterial): {
  label: string;
  variant: "default" | "muted" | "destructive" | "warning" | "success";
} {
  switch (m.quizStatus) {
    case "ready":
      return { label: "Ready for quiz", variant: "default" };
    case "extraction_too_short":
      return { label: "Ready (uses context)", variant: "warning" };
    case "not_uploaded":
      return { label: "Not uploaded yet", variant: "muted" };
    case "extraction_failed":
      return { label: "Extraction failed", variant: "destructive" };
    case "too_short":
      return { label: "Too little content", variant: "warning" };
    case "not_quiz_material":
      return { label: "Not quiz material", variant: "muted" };
    default:
      if (m.hasContent) return { label: "Ready for quiz", variant: "default" };
      if (m.contentNote?.startsWith("No readable text"))
        return { label: "Not uploaded yet", variant: "muted" };
      return { label: "Content unavailable", variant: "muted" };
  }
}

function MaterialRow({
  material,
  selectedIds,
  onToggle,
}: {
  material: LearningMaterial;
  selectedIds: string[];
  onToggle: (id: string) => void;
}) {
  const selectable = isSelectable(material);
  const checked = selectedIds.includes(material.id);
  const { label: statusLabel, variant: statusVariant } = statusBadge(material);

  return (
    <label
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-lg border border-border bg-background p-3 transition-colors",
        selectable
          ? "cursor-pointer hover:bg-accent has-[:checked]:border-primary/50"
          : "cursor-not-allowed opacity-60",
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

      {/* Hint text under the row */}
      {material.quizStatus === "extraction_too_short" ? (
        <p className="w-full basis-full pl-9 text-xs text-muted-foreground">
          Extracted text is limited — quiz will be generated using other ready
          materials from this course as supporting context.
        </p>
      ) : !selectable && (material.contentNote || material.quizStatusReason) ? (
        <p className="w-full basis-full pl-9 text-xs text-muted-foreground">
          {material.quizStatusReason || material.contentNote}
        </p>
      ) : null}
    </label>
  );
}

export function MaterialSelect({
  materials,
  selectedIds,
  onToggle,
}: MaterialSelectProps) {
  const [showOther, setShowOther] = useState(false);

  // Split into educational (selectable or nearly-selectable) vs admin/non-quiz
  const educational = materials.filter(
    (m) => m.quizStatus !== "not_quiz_material",
  );
  const nonQuiz = materials.filter(
    (m) => m.quizStatus === "not_quiz_material",
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Select Learning Materials</CardTitle>
        <CardDescription>
          Lectures, labs, revisions, slides, and notes are selectable once
          uploaded. Materials marked &ldquo;Ready (uses context)&rdquo; will
          generate a quiz using other ready materials from this course when
          their own extracted text is limited. Grades files and Moodle activity
          types cannot be used for quiz generation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {materials.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No learning materials found for this course.{" "}
            <span className="font-medium">
              Use the Chrome extension → &ldquo;Upload materials for quiz&rdquo;
              on your Moodle course page to add materials.
            </span>
          </p>
        ) : (
          <>
            {/* ── Educational materials ── */}
            {educational.length > 0 ? (
              <div className="space-y-2">
                {educational.map((m) => (
                  <MaterialRow
                    key={m.id}
                    material={m}
                    selectedIds={selectedIds}
                    onToggle={onToggle}
                  />
                ))}
              </div>
            ) : null}

            {/* ── Non-quiz materials (collapsed) ── */}
            {nonQuiz.length > 0 ? (
              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => setShowOther((v) => !v)}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showOther ? (
                    <ChevronDown className="h-3 w-3" />
                  ) : (
                    <ChevronRight className="h-3 w-3" />
                  )}
                  {showOther ? "Hide" : "Show"} {nonQuiz.length} non-quiz
                  item{nonQuiz.length === 1 ? "" : "s"} (grades, admin, forums…)
                </button>
                {showOther ? (
                  <div className="mt-2 space-y-2">
                    {nonQuiz.map((m) => (
                      <MaterialRow
                        key={m.id}
                        material={m}
                        selectedIds={selectedIds}
                        onToggle={onToggle}
                      />
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
