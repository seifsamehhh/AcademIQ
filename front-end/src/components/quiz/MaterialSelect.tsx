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

// ── Sorting helpers ────────────────────────────────────────────────────────────

const LECTURE_RE = /\blecture(?:\s*#?(\d+)|\b)/i;
const LEC_RE = /\blec(?:\s*#?(\d+)|\b)/i;
const LAB_RE = /\blab(?:\s*#?(\d+)|\b)/i;
const REVISION_RE = /\b(revision|review|summary)(?:\s*#?(\d+)|\b)/i;
const NOTES_RE =
  /\b(notes?|tutorial|handout|slides?|worksheet|chapters?|exercise|module)\b/i;

/**
 * Extract lecture/lab/revision number from title.
 * Ignores course codes (e.g. SWE423) by preferring numbers after type keywords.
 */
function extractMaterialNumber(title: string): number {
  const patterns = [
    /\blecture\s*#?(\d+)/i,
    /\blec\s*#?(\d+)/i,
    /\blab\s*#?(\d+)/i,
    /\b(?:revision|review|summary)\s*#?(\d+)/i,
    /\bchapter\s*#?(\d+)/i,
  ];
  for (const re of patterns) {
    const m = title.match(re);
    if (m?.[1]) return parseInt(m[1], 10);
  }
  const all = title.match(/\d+/g);
  if (all && all.length > 1) {
    return parseInt(all[all.length - 1], 10);
  }
  if (all?.length === 1) return parseInt(all[0], 10);
  return Infinity;
}

/**
 * Sort group (lower = shown earlier):
 *   0 Lectures · 1 Labs · 2 Revision · 3 Notes/slides · 4 Other educational · 5 Non-quiz
 */
function sortGroup(m: LearningMaterial): number {
  if (m.quizStatus === "not_quiz_material") return 5;
  const t = m.title;
  if (LECTURE_RE.test(t) || LEC_RE.test(t)) return 0;
  if (LAB_RE.test(t)) return 1;
  if (REVISION_RE.test(t)) return 2;
  if (NOTES_RE.test(t)) return 3;
  return 4;
}

function sortMaterials(list: LearningMaterial[]): LearningMaterial[] {
  return [...list].sort((a, b) => {
    const ga = sortGroup(a);
    const gb = sortGroup(b);
    if (ga !== gb) return ga - gb;
    const na = extractMaterialNumber(a.title);
    const nb = extractMaterialNumber(b.title);
    if (na !== nb) return na - nb;
    return a.title.localeCompare(b.title, undefined, { numeric: true, sensitivity: "base" });
  });
}

// ── Selectable / badge — driven by backend quizStatus only ───────────────────

function isSelectable(m: LearningMaterial): boolean {
  if (m.quizStatus === "not_quiz_material") return false;
  if (m.quizGenerationEligible === true) return true;
  if (m.quizStatus === "ready") return true;
  if (m.quizStatus === "extraction_too_short") return true;
  return false;
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
    case "not_uploaded":
      return { label: "Not uploaded yet", variant: "muted" };
    case "extraction_failed":
      return { label: "Extraction failed", variant: "destructive" };
    case "too_short":
      return { label: "Too little content", variant: "warning" };
    case "not_quiz_material":
      return { label: "Not quiz material", variant: "muted" };
    default:
      return { label: "Content unavailable", variant: "muted" };
  }
}

// ── Single material row ───────────────────────────────────────────────────────

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

// ── Main component ────────────────────────────────────────────────────────────

export function MaterialSelect({
  materials,
  selectedIds,
  onToggle,
}: MaterialSelectProps) {
  const [showOther, setShowOther] = useState(false);

  const sorted = sortMaterials(materials);
  const educational = sorted.filter((m) => m.quizStatus !== "not_quiz_material");
  const nonQuiz = sorted.filter((m) => m.quizStatus === "not_quiz_material");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Select Learning Materials</CardTitle>
        <CardDescription>
          Lectures, labs, and revisions appear first in order. Materials marked
          &ldquo;Ready for quiz&rdquo; can generate a quiz. Grades, assignments,
          and other admin Moodle items cannot be used for quiz generation.
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
            {educational.length > 0 && (
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
            )}

            {nonQuiz.length > 0 && (
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
                  {showOther ? "Hide" : "Show"} {nonQuiz.length} other Moodle
                  item{nonQuiz.length === 1 ? "" : "s"} (grades, admin, forums…)
                </button>
                {showOther && (
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
                )}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
