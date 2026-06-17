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

/**
 * Extract the first integer from a string for natural ordering.
 * "Lecture 10" → 10, "Lab 2" → 2, "Revision" → Infinity
 */
function extractNum(s: string): number {
  const m = s.match(/\d+/);
  return m ? parseInt(m[0], 10) : Infinity;
}

/**
 * Map a material title to a sort-group number (lower = shown earlier).
 *
 *   0  Lectures
 *   1  Labs
 *   2  Revision / Review / Summary
 *   3  Notes / Tutorial / Handout / Slides / Worksheet / Chapter / Exercise
 *   4  Other educational (not_quiz_material === false, but no type keyword)
 *  99  Non-quiz / admin
 */
function sortGroup(m: LearningMaterial): number {
  if (m.quizStatus === "not_quiz_material") return 99;
  const t = m.title.toLowerCase();
  // Use only a LEADING word boundary so "lecture1", "lecture#1", "lec 1" all match.
  // \blecture matches at any word boundary before the letter l, with no constraint
  // on what follows — avoids the bug where "Lecture1" (digit after e) fails \blecture\b.
  if (/\blecture|\blec\s*\d/i.test(t)) return 0;
  // \blab\b is kept strict to avoid false-positives in "syllable" etc., but also
  // accept "lab1" or "lab_1" patterns.
  if (/\blab\b|\blab\s*\d/i.test(t)) return 1;
  if (/\b(revision|review|summary)\b/i.test(t)) return 2;
  if (/\b(notes?|tutorial|handout|slides?|worksheet|chapter|exercise|module)\b/i.test(t)) return 3;
  return 4;
}

function sortMaterials(list: LearningMaterial[]): LearningMaterial[] {
  return [...list].sort((a, b) => {
    const ga = sortGroup(a);
    const gb = sortGroup(b);
    if (ga !== gb) return ga - gb;
    // Within the same group use natural numeric ordering
    const na = extractNum(a.title);
    const nb = extractNum(b.title);
    if (na !== nb) return na - nb;
    // Alphabetical fallback
    return a.title.localeCompare(b.title, undefined, { numeric: true });
  });
}

// ── A material is selectable when it is ready OR can use context-fallback ─────

function isSelectable(m: LearningMaterial): boolean {
  if (m.quizStatus === "ready") return true;
  if (m.quizStatus === "extraction_too_short") return true;
  if (!m.quizStatus && m.hasContent) return true;
  return false;
}

// ── Badge label + variant per status ─────────────────────────────────────────

function statusBadge(m: LearningMaterial): {
  label: string;
  variant: "default" | "muted" | "destructive" | "warning";
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

      {/* Hint text under the row */}
      {material.quizStatus === "extraction_too_short" ? (
        <p className="w-full basis-full pl-9 text-xs text-muted-foreground">
          Extracted text is limited — quiz will use other ready materials from
          this course as supporting context.
        </p>
      ) : !selectable && (material.contentNote || material.quizStatusReason) ? (
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
          Lectures, labs, revisions, notes, and slides are sorted in order.
          Materials marked &ldquo;Ready (uses context)&rdquo; will generate a
          quiz using other ready materials from this course when their own
          extracted text is limited. Grades files and Moodle activity types
          cannot be used for quiz generation.
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
            {/* ── Educational materials, sorted ── */}
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

            {/* ── Non-quiz materials (collapsed by default) ── */}
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
                  {showOther ? "Hide" : "Show"} {nonQuiz.length} non-quiz
                  item{nonQuiz.length === 1 ? "" : "s"} (grades, admin,
                  forums…)
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
