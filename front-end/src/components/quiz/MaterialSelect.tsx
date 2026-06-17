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

// ── Sorting (mirrors backend material_quiz_display.py) ───────────────────────

const LECTURE_TYPE_RE = /\b(?:lecture|lec)(?:\s*#?\d|\b)/i;
const LAB_TYPE_RE = /\blab(?:\s*#?\d|\b)/i;
const REVISION_TYPE_RE = /\b(?:revision|review|summary)(?:\s*#?\d|\b)/i;
const NOTES_TYPE_RE =
  /\b(?:notes?|tutorials?|handouts?|slides?|worksheets?|chapters?|exercises?|modules?|week\b|problems?\b)/i;

const LECTURE_NUM_RE = /\b(?:lecture|lec)\s*#?(\d+)/i;
const LAB_NUM_RE = /\blab(?:\s+(?:assignment\s*)?)?\s*#?(\d+)/i;
const REVISION_NUM_RE = /\b(?:revision|review|summary)\s*#?(\d+)/i;
const CHAPTER_NUM_RE = /\bchapters?\s*#?(\d+)/i;
const WEEK_NUM_RE = /\bweek\s*#?(\d+)/i;

function extractMaterialNumber(title: string): number {
  const patterns = [
    LECTURE_NUM_RE,
    LAB_NUM_RE,
    REVISION_NUM_RE,
    CHAPTER_NUM_RE,
    WEEK_NUM_RE,
  ];
  for (const re of patterns) {
    const m = title.match(re);
    if (m?.[1]) return parseInt(m[1], 10);
  }
  return 9999;
}

function sortGroupLocal(m: LearningMaterial): number {
  if (m.isNonQuizMaterial || m.quizStatus === "not_quiz_material") return 5;
  const t = m.title;
  if (LECTURE_TYPE_RE.test(t)) return 0;
  if (LAB_TYPE_RE.test(t)) return 1;
  if (REVISION_TYPE_RE.test(t)) return 2;
  if (NOTES_TYPE_RE.test(t)) return 3;
  return 4;
}

function sortGroup(m: LearningMaterial): number {
  if (typeof m.sortGroup === "number") return m.sortGroup;
  return sortGroupLocal(m);
}

function sortNumber(m: LearningMaterial): number {
  if (typeof m.sortNumber === "number" && m.sortNumber < 9999) return m.sortNumber;
  return extractMaterialNumber(m.title);
}

function sortMaterials(list: LearningMaterial[]): LearningMaterial[] {
  return [...list].sort((a, b) => {
    const ga = sortGroup(a);
    const gb = sortGroup(b);
    if (ga !== gb) return ga - gb;
    const na = sortNumber(a);
    const nb = sortNumber(b);
    if (na !== nb) return na - nb;
    return a.title.localeCompare(b.title, undefined, { numeric: true, sensitivity: "base" });
  });
}

function isMainListMaterial(m: LearningMaterial): boolean {
  if (m.visibleInMainList === true) return true;
  if (m.visibleInOtherItems === true) return false;
  return !m.isNonQuizMaterial && m.quizStatus !== "not_quiz_material";
}

function isOtherMoodleItem(m: LearningMaterial): boolean {
  if (m.visibleInOtherItems === true) return true;
  if (m.visibleInMainList === true) return false;
  return m.isNonQuizMaterial === true || m.quizStatus === "not_quiz_material";
}

function isSelectable(m: LearningMaterial): boolean {
  return m.quizStatus === "ready" && m.quizGenerationEligible === true;
}

function statusBadge(m: LearningMaterial): {
  label: string;
  variant: "default" | "muted" | "destructive" | "warning";
} {
  switch (m.quizStatus) {
    case "ready":
      return { label: "Ready for quiz", variant: "default" };
    case "extraction_too_short":
      return { label: "Extraction too short", variant: "warning" };
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

      {!selectable && (material.quizStatusReason || material.contentNote) ? (
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

  const sorted = sortMaterials(materials);
  const mainList = sorted.filter(isMainListMaterial);
  const otherItems = sorted.filter(isOtherMoodleItem);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Select Learning Materials</CardTitle>
        <CardDescription>
          Lectures, labs, and revisions appear first in order. Only materials
          marked &ldquo;Ready for quiz&rdquo; can generate a quiz from their own
          content. Admin and project files are listed under Other Moodle items.
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
                  item{otherItems.length === 1 ? "" : "s"} (grades, admin, forums…)
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
