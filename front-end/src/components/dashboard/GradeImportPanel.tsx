"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { api } from "@/lib/api";
import type { Course, DemoCourseResult } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const DEFAULT_GRADE_LABEL = "Midterm scoring";

/** Current 26S semester courses — editable midterm scores. */
export const CURRENT_26S_COURSES = [
  { courseId: "666", courseName: "Advanced Artificial Intelligence - 26S" },
  { courseId: "808", courseName: "Designing Intelligent Agents - 26S" },
  { courseId: "478", courseName: "Knowledge Representation and Reasoning - 26S" },
  { courseId: "670", courseName: "Machine Learning - 26S" },
  { courseId: "462", courseName: "Mobile Device Programming - 26S" },
] as const;

interface Props {
  courses: Course[];
  courseResults?: DemoCourseResult[];
  onSaved?: () => void;
}

function formatGradeInput(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "";
  return String(Number(value.toFixed(2)));
}

export function GradeImportPanel({ courses, courseResults, onSaved }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  const resultsById = useMemo(
    () =>
      new Map(
        (courseResults ?? []).map((c) => [String(c.courseId ?? ""), c]),
      ),
    [courseResults],
  );

  const semesterRows = useMemo(() => {
    return CURRENT_26S_COURSES.map((row) => {
      const fromResults = resultsById.get(row.courseId);
      const fromCourses = courses.find((c) => c.id === row.courseId);
      return {
        courseId: row.courseId,
        courseName: fromCourses?.name ?? row.courseName,
        currentGrade: fromResults?.grade,
        currentLabel: fromResults?.gradeLabel,
      };
    });
  }, [courses, resultsById]);

  const [rowGrades, setRowGrades] = useState<Record<string, string>>({});
  const [rowLabels, setRowLabels] = useState<Record<string, string>>({});

  useEffect(() => {
    const grades: Record<string, string> = {};
    const labels: Record<string, string> = {};
    for (const row of semesterRows) {
      grades[row.courseId] = formatGradeInput(row.currentGrade);
      labels[row.courseId] = row.currentLabel ?? DEFAULT_GRADE_LABEL;
    }
    setRowGrades(grades);
    setRowLabels(labels);
  }, [semesterRows]);

  const [courseId, setCourseId] = useState(courses[0]?.id ?? "");
  const [courseName, setCourseName] = useState(courses[0]?.name ?? "");
  const [grade, setGrade] = useState("");
  const [gradeLabel, setGradeLabel] = useState(DEFAULT_GRADE_LABEL);

  useEffect(() => {
    const selected = courses.find((c) => c.id === courseId);
    if (selected) {
      setCourseName(selected.name);
      const existing = resultsById.get(courseId);
      if (existing?.grade != null) {
        setGrade(formatGradeInput(existing.grade));
      }
      if (existing?.gradeLabel) {
        setGradeLabel(existing.gradeLabel);
      }
    }
  }, [courseId, courses, resultsById]);

  async function saveGrade(payload: {
    course_id: string;
    course_name: string;
    grade_percentage: number;
    grade_label: string;
  }) {
    await api.upsertManualGrade(payload);
  }

  async function handleRowSave(row: { courseId: string; courseName: string }) {
    const pct = parseFloat(rowGrades[row.courseId] ?? "");
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
        grade_label: rowLabels[row.courseId]?.trim() || DEFAULT_GRADE_LABEL,
      });
      setStatus(`Saved midterm grade for ${row.courseName}.`);
      onSaved?.();
      setExpanded(false);
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
      setStatus("Midterm grade saved.");
      setGrade("");
      onSaved?.();
      setExpanded(false);
    } catch {
      setStatus("Could not save grade. Sign in and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setExpanded((open) => !open)}
        className="flex w-full items-center justify-between rounded-lg border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
        aria-expanded={expanded}
      >
        <span>Edit grades manually</span>
        <ChevronDown
          className={`h-4 w-4 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`}
          aria-hidden
        />
      </button>

      {status && !expanded ? (
        <p className="text-sm text-muted-foreground px-1">{status}</p>
      ) : null}

      {expanded ? (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Manage uploaded grades</CardTitle>
            <CardDescription>
              Update current 26S midterm scores. Midterm scoring overrides Moodle course
              totals on the Dashboard for this semester.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <p className="text-sm font-medium text-foreground">Current 26S courses</p>
              {semesterRows.map((row) => (
                <div
                  key={row.courseId}
                  className="grid gap-3 rounded-lg border border-border bg-muted/20 p-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end"
                >
                  <div className="space-y-1 lg:col-span-2">
                    <p className="text-xs text-muted-foreground">{row.courseId}</p>
                    <p className="text-sm font-medium leading-snug">{row.courseName}</p>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor={`sem-grade-${row.courseId}`} className="text-xs">
                      Grade %
                    </Label>
                    <Input
                      id={`sem-grade-${row.courseId}`}
                      type="number"
                      min={0}
                      max={100}
                      step={0.01}
                      value={rowGrades[row.courseId] ?? ""}
                      onChange={(e) =>
                        setRowGrades((prev) => ({
                          ...prev,
                          [row.courseId]: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor={`sem-label-${row.courseId}`} className="text-xs">
                      Label
                    </Label>
                    <Input
                      id={`sem-label-${row.courseId}`}
                      value={rowLabels[row.courseId] ?? DEFAULT_GRADE_LABEL}
                      onChange={(e) =>
                        setRowLabels((prev) => ({
                          ...prev,
                          [row.courseId]: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div>
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      disabled={saving}
                      onClick={() => handleRowSave(row)}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            <div className="space-y-3 border-t border-border pt-4">
              <p className="text-sm font-medium text-foreground">Other course</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1">
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
                      placeholder="Course ID"
                      value={courseId}
                      onChange={(e) => setCourseId(e.target.value)}
                    />
                  )}
                </div>
                <div className="space-y-1">
                  <Label htmlFor="grade-import-name">Course name</Label>
                  <Input
                    id="grade-import-name"
                    value={courseName}
                    onChange={(e) => setCourseName(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="grade-import-pct">Grade %</Label>
                  <Input
                    id="grade-import-pct"
                    type="number"
                    min={0}
                    max={100}
                    step={0.01}
                    value={grade}
                    onChange={(e) => setGrade(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="grade-import-label">Label</Label>
                  <Input
                    id="grade-import-label"
                    value={gradeLabel}
                    onChange={(e) => setGradeLabel(e.target.value)}
                  />
                </div>
              </div>
              <Button type="button" onClick={handleSave} disabled={saving} size="sm">
                {saving ? "Saving…" : "Save grade"}
              </Button>
            </div>

            {status && expanded ? (
              <p className="text-sm text-muted-foreground">{status}</p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
