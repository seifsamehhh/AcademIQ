import { useState } from "react";
import { ChevronDown, ChevronRight, FileText } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { LearningMaterial } from "@/lib/types";
import {
  displayMaterial,
  deduplicateMaterials,
  isEducationalKind,
  isMainListLearningMaterial,
  isReadyMaterial,
  isSkippedEducational,
  isStandaloneExercise,
  materialSubtitle,
  normalizeMaterialForDisplay,
  sortMaterialsForDisplay,
} from "@/lib/materialDisplay";

interface MaterialSelectProps {
  materials: LearningMaterial[];
  selectedIds: string[];
  onToggle: (id: string) => void;
}

const NO_READY_MESSAGE =
  "No quiz-ready learning materials are available yet for this course.";

function isVisibleMaterial(m: LearningMaterial): boolean {
  if (m.missingFromDb) return false;
  if (m.kind === "MISSING") return false;
  if (m.source === "missing_from_db") return false;
  return true;
}

function isOtherMoodleItem(m: LearningMaterial): boolean {
  if (isStandaloneExercise(m)) return true;
  if (m.visibleInOtherItems === true) return true;
  if (m.isNonQuizMaterial === true || m.quizStatus === "not_quiz_material") return true;
  if (!isEducationalKind(m)) return true;
  return false;
}

export function isMaterialSelectable(m: LearningMaterial): boolean {
  if (!isVisibleMaterial(m)) return false;
  const n = normalizeMaterialForDisplay(m);
  if (!isReadyMaterial(n)) return false;
  return n.quizGenerationEligible === true;
}

function statusBadge(m: LearningMaterial): {
  label: string;
  variant: "default" | "muted" | "destructive" | "warning";
} {
  const n = normalizeMaterialForDisplay(m);
  switch (n.quizStatus) {
    case "ready":
      return { label: "Ready for quiz", variant: "default" };
    case "limited_ready":
      return { label: "Ready limited", variant: "warning" };
    case "not_quiz_material":
      return { label: "Not quiz material", variant: "muted" };
    case "not_uploaded":
      return { label: "Not synced yet", variant: "muted" };
    case "extraction_failed":
      return { label: "Could not extract", variant: "muted" };
    case "extraction_too_short":
    case "not_enough_readable_text":
      return { label: "Not enough content", variant: "muted" };
    default:
      return { label: "Not available", variant: "muted" };
  }
}

function MaterialRow({
  material,
  selectedIds,
  onToggle,
  disabled = false,
}: {
  material: LearningMaterial;
  selectedIds: string[];
  onToggle: (id: string) => void;
  disabled?: boolean;
}) {
  const display = displayMaterial(material);
  const selectable = !disabled && isMaterialSelectable(material);
  const checked = selectedIds.includes(material.id);
  const { label: statusLabel, variant: statusVariant } = statusBadge(material);
  const subtitle = materialSubtitle(material);

  return (
    <label
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-lg border border-border/60 bg-background/60 p-3 transition-colors",
        selectable
          ? "cursor-pointer hover:border-primary/30 hover:bg-primary/5 has-[:checked]:border-primary/50"
          : "cursor-not-allowed opacity-55",
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
        {display.title}
      </span>

      <Badge variant={statusVariant}>{statusLabel}</Badge>

      {subtitle ? (
        <p className="w-full basis-full pl-9 text-[11px] text-muted-foreground/80">
          {subtitle}
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
  const [showSkipped, setShowSkipped] = useState(false);

  const visible = deduplicateMaterials(
    materials.filter(isVisibleMaterial).map(normalizeMaterialForDisplay),
  );
  const readyList = sortMaterialsForDisplay(
    visible.filter((m) => isMainListLearningMaterial(m)),
  );
  const skippedEducational = visible.filter(isSkippedEducational);
  const otherItems = visible.filter(isOtherMoodleItem);

  return (
    <div className="mc-card p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-foreground">Learning materials</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Select lectures, labs, or revision materials marked Ready for quiz or Ready
          limited. Quiz questions are generated from the selected file only.
        </p>
      </div>
      <div className="space-y-2">
        {visible.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No learning materials found for this course. Sync materials from Moodle
            using the AcademIQ Chrome extension.
          </p>
        ) : (
          <>
            {readyList.length === 0 ? (
              <p className="text-sm text-muted-foreground rounded-md border border-border bg-muted/40 px-3 py-2">
                {NO_READY_MESSAGE}
              </p>
            ) : (
              <div className="space-y-2">
                {readyList.map((m) => (
                  <MaterialRow
                    key={m.id}
                    material={m}
                    selectedIds={selectedIds}
                    onToggle={onToggle}
                  />
                ))}
              </div>
            )}

            {skippedEducational.length > 0 && (
              <div className="mt-3">
                <button
                  type="button"
                  onClick={() => setShowSkipped((v) => !v)}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showSkipped ? (
                    <ChevronDown className="h-3 w-3" />
                  ) : (
                    <ChevronRight className="h-3 w-3" />
                  )}
                  Skipped {skippedEducational.length} item
                  {skippedEducational.length === 1 ? "" : "s"} (not ready yet)
                </button>
                {showSkipped && (
                  <div className="mt-2 space-y-2">
                    {sortMaterialsForDisplay(skippedEducational).map((m) => (
                      <MaterialRow
                        key={m.id}
                        material={m}
                        selectedIds={selectedIds}
                        onToggle={onToggle}
                        disabled
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {otherItems.length > 0 && (
              <div className="mt-3">
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
                  Other Moodle items ({otherItems.length}) — assignments, forums,
                  exercises, grades, admin links
                </button>
                {showOther && (
                  <div className="mt-2 space-y-2">
                    {otherItems.map((m) => (
                      <MaterialRow
                        key={m.id}
                        material={m}
                        selectedIds={selectedIds}
                        onToggle={onToggle}
                        disabled
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
