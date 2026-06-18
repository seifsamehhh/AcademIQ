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

const NO_READY_MESSAGE =
  "No quiz-ready learning materials are available yet for this course.";

const STATUS_HELP: Record<string, string> = {
  not_uploaded:
    "File detected from Moodle, but readable content has not been extracted yet.",
  extraction_failed: "Content could not be extracted from this Moodle file.",
  not_enough_readable_text:
    "Text was extracted, but it does not contain enough structured educational content for a reliable quiz.",
  extraction_too_short:
    "Text was extracted, but it does not contain enough structured educational content for a reliable quiz.",
};

/** Hide synthetic / debug rows from the demo UI. */
function isVisibleMaterial(m: LearningMaterial): boolean {
  if (m.missingFromDb) return false;
  if (m.kind === "MISSING") return false;
  if (m.source === "missing_from_db") return false;
  return true;
}

/** Backend returns materials pre-sorted; preserve that order when splitting lists. */
function preserveApiOrder(
  all: LearningMaterial[],
  predicate: (m: LearningMaterial) => boolean,
): LearningMaterial[] {
  return all.filter(predicate);
}

function isMainListMaterial(m: LearningMaterial): boolean {
  if (m.visibleInOtherItems === true) return false;
  if (m.visibleInMainList === true) return true;
  return !m.isNonQuizMaterial && m.quizStatus !== "not_quiz_material";
}

function isOtherMoodleItem(m: LearningMaterial): boolean {
  if (m.visibleInOtherItems === true) return true;
  if (m.visibleInMainList === true) return false;
  return m.isNonQuizMaterial === true || m.quizStatus === "not_quiz_material";
}

export function isMaterialSelectable(m: LearningMaterial): boolean {
  if (!isVisibleMaterial(m)) return false;
  if (m.quizStatus === "not_quiz_material") return false;
  if (m.quizStatus === "ready" || m.quizStatus === "limited_ready") {
    return m.quizGenerationEligible === true;
  }
  return false;
}

function statusBadge(m: LearningMaterial): {
  label: string;
  variant: "default" | "muted" | "destructive" | "warning";
} {
  switch (m.quizStatus) {
    case "ready":
      return { label: "Ready for quiz", variant: "default" };
    case "limited_ready":
      return { label: "Ready, limited", variant: "warning" };
    case "extraction_too_short":
      return { label: "Not enough readable text", variant: "warning" };
    case "not_enough_readable_text":
      return { label: "Not enough readable text", variant: "warning" };
    case "not_uploaded":
      return { label: "Not uploaded yet", variant: "muted" };
    case "extraction_failed":
      return { label: "Extraction failed", variant: "destructive" };
    case "unsupported":
      return { label: "Unsupported file type", variant: "warning" };
    case "too_short":
      return { label: "Too little content", variant: "warning" };
    case "not_quiz_material":
      return { label: "Not quiz material", variant: "muted" };
    default:
      return { label: "Not available for quiz", variant: "muted" };
  }
}

function getHelpText(m: LearningMaterial, selectable: boolean): string | null {
  if (selectable) {
    if (m.quizStatus === "limited_ready" && m.quizStatusReason) {
      const note = m.quizStatusReason.trim();
      if (note && !note.includes("course context") && !note.includes("course-context")) {
        return note;
      }
    }
    return null;
  }
  if (m.quizStatus && STATUS_HELP[m.quizStatus]) {
    return STATUS_HELP[m.quizStatus];
  }
  return null;
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
  const selectable = isMaterialSelectable(material);
  const checked = selectedIds.includes(material.id);
  const { label: statusLabel, variant: statusVariant } = statusBadge(material);
  const helpText = getHelpText(material, selectable);

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

      {selectable && material.source === "moodle_sync" ? (
        <Badge variant="muted">Moodle</Badge>
      ) : null}

      {helpText ? (
        <p className="w-full basis-full pl-9 text-xs text-muted-foreground">
          {helpText}
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

  const visible = materials.filter(isVisibleMaterial);
  const mainList = preserveApiOrder(visible, isMainListMaterial);
  const otherItems = preserveApiOrder(visible, isOtherMoodleItem);
  const selectableCount = visible.filter(isMaterialSelectable).length;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Learning materials</CardTitle>
        <CardDescription>
          Lectures, labs, revisions, and notes appear below. Select materials
          marked Ready for quiz or Ready, limited to generate a quiz from that
          file&apos;s content only.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {visible.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No learning materials found for this course. Sync materials from
            Moodle using the AcademIQ Chrome extension.
          </p>
        ) : (
          <>
            {selectableCount === 0 ? (
              <p className="text-sm text-muted-foreground rounded-md border border-border bg-muted/40 px-3 py-2">
                {NO_READY_MESSAGE}
              </p>
            ) : null}

            {mainList.length > 0 && (
              <div className="space-y-2">
                {mainList.map((m) => (
                  <MaterialRow
                    key={m.id}
                    material={m}
                    selectedIds={selectedIds}
                    onToggle={onToggle}
                  />
                ))}
              </div>
            )}

            {otherItems.length > 0 && (
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
                  {showOther ? "Hide" : "Show"} {otherItems.length} other Moodle
                  item{otherItems.length === 1 ? "" : "s"} (grades, submissions,
                  project requirements, criteria, rubrics, forums, folders,
                  admin files)
                </button>
                {showOther && (
                  <div className="mt-2 space-y-2">
                    {otherItems.map((m) => (
                      <MaterialRow
                        key={m.id}
                        material={m}
                        selectedIds={selectedIds}
                        onToggle={onToggle}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
