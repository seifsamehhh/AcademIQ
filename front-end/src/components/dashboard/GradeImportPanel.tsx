"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Course } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  courses: Course[];
  onSaved?: () => void;
}

export function GradeImportPanel({ courses, onSaved }: Props) {
  const [courseId, setCourseId] = useState(courses[0]?.id ?? "");
  const [grade, setGrade] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  const selected = courses.find((c) => c.id === courseId);

  async function handleSave() {
    const pct = parseFloat(grade);
    if (!courseId || Number.isNaN(pct) || pct < 0 || pct > 100) {
      setStatus("Enter a course and grade between 0 and 100.");
      return;
    }
    setSaving(true);
    setStatus("");
    try {
      await api.upsertManualGrade({
        course_id: courseId,
        course_name: selected?.name ?? "",
        grade_percentage: pct,
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
          Demo-only: stores an uploaded grade transcript when Moodle does not publish grades.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="grade-import-course">Course</Label>
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
        </div>
        <Button type="button" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save uploaded grade"}
        </Button>
        {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      </CardContent>
    </Card>
  );
}
