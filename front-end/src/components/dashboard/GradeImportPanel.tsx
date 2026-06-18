"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Course, DemoCourseResult } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const DEFAULT_GRADE_LABEL = "Uploaded grade transcript";

/** Courses commonly missing Moodle-published grades in the demo account. */
const PREFILL_MISSING = [
  { courseId: "808", courseName: "Designing Intelligent Agents - 26S" },
  { courseId: "670", courseName: "Machine Learning - 26S" },
] as const;

interface Props {
  courses: Course[];
  courseResults?: DemoCourseResult[];
  onSaved?: () => void;
}

function courseHasDisplayGrade(course: DemoCourseResult | undefined): boolean {
  if (!course) return false;
  return (
    course.gradeAvailable === true ||
    (course.gradeAvailable !== false && course.grade != null)
  );
}

export function GradeImportPanel({ courses, courseResults, onSaved }: Props) {
  const missingPrefill = useMemo(() => {
    const byId = new Map(
      (courseResults ?? []).map((c) => [String(c.courseId ?? ""), c]),
    );
    return PREFILL_MISSING.filter((row) => {
      const existing = byId.get(row.courseId);
      return !courseHasDisplayGrade(existing);
    });
  }, [courseResults]);

  const [quickGrades, setQuickGrades] = useState<Record<string, string>>({});
  const [quickLabels, setQuickLabels] = useState<Record<string, string>>({});

  const [courseId, setCourseId] = useState(courses[0]?.id ?? "");
  const [courseName, setCourseName] = useState(courses[0]?.name ?? "");
  const [grade, setGrade] = useState("");
  const [gradeLabel, setGradeLabel] = useState(DEFAULT_GRADE_LABEL);
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const selected = courses.find((c) => c.id === courseId);
    if (selected) {
      setCourseName(selected.name);
    }
  }, [courseId, courses]);

  async function saveGrade(payload: {
    course_id: string;
    course_name: string;
    grade_percentage: number;
    grade_label: string;
  }) {
    await api.upsertManualGrade(payload);
  }

  async function handleQuickSave(row: { courseId: string; courseName: string }) {
    const pct = parseFloat(quickGrades[row.courseId] ?? "");
    if (Number.isNaN(pct) || pct < 0 || pct > 100) {
      setStatus(`Enter a grade between 0 and 100 for ${row.courseName}.`);
      return;
    }
    setSaving(true);
    setStatus("");
    try {
      await saveGrade({
        course_id: row.courseId,
        course_name: row.courseName,
        grade_percentage: pct,
        grade_label: quickLabels[row.courseId]?.trim() || DEFAULT_GRADE_LABEL,
      });
      setStatus(`Saved uploaded grade for ${row.courseName}.`);
      setQuickGrades((prev) => ({ ...prev, [row.courseId]: "" }));
      onSaved?.();
    } catch {
      setStatus("Could not save grade. Sign in and try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSave() {
    const pct = parseFloat(grade);
    if (!courseId.trim() || Number.isNaN(pct) || pct < 0 || pct > 100) {
      setStatus("Enter course ID and a grade between 0 and 100.");
      return;
    }
    setSaving(true);
    setStatus("");
    try {
      await saveGrade({
        course_id: courseId.trim(),
        course_name: courseName.trim(),
        grade_percentage: pct,
        grade_label: gradeLabel.trim() || DEFAULT_GRADE_LABEL,
      });
      setStatus("Uploaded grade transcript saved.");
      setGrade("");
      onSaved?.();
    } catch {
      setStatus("Could not save grade. Sign in and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Add missing course grade</CardTitle>
        <CardDescription>
          Store an uploaded grade transcript when Moodle does not publish a course grade.
          Grades are labeled as uploaded transcript data, not official Moodle grades.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {missingPrefill.length ? (
          <div className="space-y-4">
            <p className="text-sm font-medium text-foreground">
              Quick add — courses without a synced Moodle grade
            </p>
            {missingPrefill.map((row) => (
              <div
                key={row.courseId}
                className="grid gap-3 rounded-lg border border-border bg-muted/30 p-4 sm:grid-cols-2 lg:grid-cols-4"
              >
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Course ID</Label>
                  <p className="text-sm font-medium">{row.courseId}</p>
                </div>
                <div className="space-y-1 sm:col-span-1 lg:col-span-1">
                  <Label className="text-xs text-muted-foreground">Course name</Label>
                  <p className="text-sm">{row.courseName}</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`quick-grade-${row.courseId}`}>Grade %</Label>
                  <Input
                    id={`quick-grade-${row.courseId}`}
                    type="number"
                    min={0}
                    max={100}
                    step={0.1}
                    placeholder="e.g. 68"
                    value={quickGrades[row.courseId] ?? ""}
                    onChange={(e) =>
                      setQuickGrades((prev) => ({
                        ...prev,
                        [row.courseId]: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`quick-label-${row.courseId}`}>Grade label</Label>
                  <Input
                    id={`quick-label-${row.courseId}`}
                    value={quickLabels[row.courseId] ?? DEFAULT_GRADE_LABEL}
                    onChange={(e) =>
                      setQuickLabels((prev) => ({
                        ...prev,
                        [row.courseId]: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="sm:col-span-2 lg:col-span-4">
                  <Button
                    type="button"
                    size="sm"
                    disabled={saving}
                    onClick={() => handleQuickSave(row)}
                  >
                    Save {row.courseId}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : null}

        <div className="space-y-4">
          <p className="text-sm font-medium text-foreground">Any course</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="grade-import-course">Course</Label>
              {courses.length ? (
                <select
                  id="grade-import-course"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={courseId}
                  onChange={(e) => setCourseId(e.target.value)}
                >
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  id="grade-import-course-id"
                  placeholder="Course ID e.g. 808"
                  value={courseId}
                  onChange={(e) => setCourseId(e.target.value)}
                />
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="grade-import-name">Course name</Label>
              <Input
                id="grade-import-name"
                value={courseName}
                onChange={(e) => setCourseName(e.target.value)}
                placeholder="Course name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="grade-import-pct">Grade percentage</Label>
              <Input
                id="grade-import-pct"
                type="number"
                min={0}
                max={100}
                step={0.1}
                placeholder="e.g. 72"
                value={grade}
                onChange={(e) => setGrade(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="grade-import-label">Grade label</Label>
              <Input
                id="grade-import-label"
                value={gradeLabel}
                onChange={(e) => setGradeLabel(e.target.value)}
              />
            </div>
          </div>
          <Button type="button" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save uploaded grade"}
          </Button>
        </div>

        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
